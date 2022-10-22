import argparse
import json
import logging
import signal
import sys
import threading
import traceback
from enum import Enum, auto
from pathlib import Path
from time import time, sleep
from typing import List, Optional

# noinspection Mypy
import numpy
from more_itertools import first_true, pairwise
from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from robot_cameraman.camera_controller import ElapsedTime
from robot_cameraman.camera_observable import \
    PanasonicCameraObservable, ObservableCameraProperty
from robot_cameraman.live_view import PanasonicLiveView
from robot_cameraman.zoom import ZoomStep


class Arguments(Protocol):
    liveView: str
    ip: str
    port: int
    identifyToPanasonicCameraAs: str
    output: Path
    debug: bool
    cameraMinFocalLength: float
    maxZoomRatio: float


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser(
        description="Analyze zoom steps and speed.")
    parser.add_argument('--liveView', type=str,
                        default='Panasonic',
                        help="The live view (camera) to use."
                             "Either 'Panasonic' or 'Webcam'")
    parser.add_argument('--ip', type=str,
                        default='0.0.0.0',
                        help="UDP Socket IP address of Panasonic live view.")
    parser.add_argument('--port', type=int,
                        default=49199,
                        help="UDP Socket port of Panasonic live view.")
    parser.add_argument('--identifyToPanasonicCameraAs', type=str,
                        help="When connecting to the camera for remote control,"
                             " identify ourselves with this name. Required on"
                             "certain cameras including DC-FZ80."
                        )
    parser.add_argument('--output',
                        type=Path,
                        default=None,
                        help="JSON output file of analysis results.")
    parser.add_argument('--debug',
                        action='store_true',
                        help="Enable debug logging")
    parser.add_argument('--cameraMinFocalLength',
                        type=float, default=6.0,
                        help="Minimum focal length in millimeter"
                             "of the used camera. The actual focal length"
                             "and not the 35mm equivalent is expected.")
    parser.add_argument('--maxZoomRatio',
                        type=float, default=14.3,
                        help="Maximum zoom ratio of the used camera.")
    # noinspection PyTypeChecker
    return parser.parse_args()


def quit(sig=None, frame=None, exit_code=0):
    global camera_manager
    print("Exiting...")
    if threading.current_thread() != camera_manager:
        print('wait for camera manager thread')
        camera_manager.cancel()
        camera_manager.join()
        exit(exit_code)


def configure_logging():
    # TODO filename or output directory as program argument
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.ERROR,
        filename=f'{args.output}.log' if args.output else None,
        filemode='w',
        format='%(asctime)s %(name)-50s %(levelname)-8s %(message)s')
    console = logging.StreamHandler()
    # TODO level as program argument
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(levelname)-8s %(name)-12s: %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)


class ZoomStepJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ZoomStep):
            return obj.__dict__
        # Base class default() raises TypeError:
        return json.JSONEncoder.default(self, obj)


class ZoomSpeed(Enum):
    SLOW = auto()
    FAST = auto()


class ZoomAnalyzerCameraController:
    class _State(Enum):
        ANALYZE_SLOW = auto()
        ZOOM_OUT = auto()
        STOPPED = auto()
        CANCELED = auto()

    zoom_speed: ZoomSpeed
    _state: _State
    _camera_manager: PanasonicCameraManager
    _max_zoom_ratio: float
    _previous_zoom_ratio: Optional[float]
    _current_zoom_ratio: Optional[float]
    live_view: PanasonicLiveView
    zoom_steps: List[ZoomStep]

    # noinspection PyShadowingNames
    def __init__(
            self,
            camera_manager: PanasonicCameraManager,
            max_zoom_ratio: float,
            zoom_speed: ZoomSpeed,
            live_view: PanasonicLiveView):
        self.live_view = live_view
        self._current_zoom_ratio = None
        self.zoom_speed = zoom_speed
        self._max_zoom_ratio = max_zoom_ratio
        self._state = self._State.STOPPED
        self._camera_manager = camera_manager
        self._elapsed_time = ElapsedTime()
        self._previous_zoom_ratio = None
        self.zoom_steps = []

    def start(self):
        assert self._state == self._State.STOPPED
        self._previous_zoom_ratio = None
        self.zoom_steps = []
        self._state = self._State.ANALYZE_SLOW
        if self._camera_manager.camera is None:
            print('waiting for camera connection')
            while self._camera_manager.camera is None:
                sleep(1)
                print('...')
            print('successfully connected to camera')
            print('waiting 3 second for camera to get ready')
            sleep(3)
        else:
            print('camera already connected')
        print(f"start analysis")
        self._zoom_in()
        self._elapsed_time.reset()

    def cancel(self):
        self._state = self._State.CANCELED
        print(f'cancel zoom analyzer')
        self._zoom_out_completely()
        self._state = self._State.STOPPED
        print(f'canceled zoom analyzer')

    def _zoom_out_completely(self):
        print("zoom out completely")
        self._camera_manager.camera.zoom_out_fast()
        while self._current_zoom_ratio != 1.0:
            self.live_view.image()
            print(f"... current zoom ratio is {self._current_zoom_ratio}")


    def is_stopped(self):
        return self._state == self._State.STOPPED

    def _zoom_in(self):
        if self.zoom_speed == ZoomSpeed.SLOW:
            print(f"zoom in slow")
            self._camera_manager.camera.zoom_in_slow()
        elif self.zoom_speed == ZoomSpeed.FAST:
            print(f"zoom in fast")
            self._camera_manager.camera.zoom_in_fast()
        else:
            raise Exception(f"unknown zoom speed {self.zoom_speed}")

    def _zoom_out(self):
        if self.zoom_speed == ZoomSpeed.SLOW:
            print(f"zoom out slow")
            self._camera_manager.camera.zoom_out_slow()
        elif self.zoom_speed == ZoomSpeed.FAST:
            print(f"zoom out fast")
            self._camera_manager.camera.zoom_out_fast()
        else:
            raise Exception(f"unknown zoom speed {self.zoom_speed}")

    def on_zoom_ratio(self, zoom_ratio: float):
        self._current_zoom_ratio = zoom_ratio
        if self._state in (self._State.STOPPED, self._State.CANCELED):
            return
        if self._state == self._State.ZOOM_OUT:
            if zoom_ratio == 1:
                self._state = self._State.STOPPED
                self.update_zoom_out_time(zoom_ratio)
        elif self._previous_zoom_ratio != zoom_ratio:
            zoom_in_time = 0 if zoom_ratio == 1 else self._elapsed_time.update()
            self.zoom_steps.append(
                ZoomStep(zoom_ratio=zoom_ratio,
                         zoom_in_time=zoom_in_time))
            print(f'zoomed in to {zoom_ratio:4.1f} after {zoom_in_time}')
        if zoom_ratio == self._max_zoom_ratio:
            self._get_zoom_step_of_ratio(zoom_ratio).zoom_out_time = 0
            self._zoom_out()
            self._state = self._State.ZOOM_OUT
            self._elapsed_time.reset()
        elif (self._state == self._State.ZOOM_OUT
              and self._previous_zoom_ratio != zoom_ratio):
            self.update_zoom_out_time(zoom_ratio)
        self._previous_zoom_ratio = zoom_ratio

    def update_zoom_out_time(self, zoom_ratio):
        zoom_out_time = self._elapsed_time.update()
        print(f'zoomed out to {zoom_ratio:4.1f} after {zoom_out_time}')
        zoom_step = self._get_zoom_step_of_ratio(zoom_ratio)
        assert zoom_step is not None, (
            f"could not find ZoomStep of zoom ratio {zoom_ratio}"
            f" when zooming out from {self._previous_zoom_ratio}")
        zoom_step.zoom_out_time = zoom_out_time

    def _get_zoom_step_of_ratio(self, zoom_ratio: float):
        return first_true(
            self.zoom_steps,
            None,
            lambda zoom_step: zoom_step.zoom_ratio == zoom_ratio)


class ZoomToStepException(Exception):
    def __init__(
            self,
            expected_zoom_ratio: float,
            actual_zoom_ratio: float,
            time_after_zoom_has_been_stopped: float) -> None:
        super().__init__(
            f'measurement of zoom steps is not reliable:'
            f' tried to stop zoom at ratio {expected_zoom_ratio},'
            f' after {time_after_zoom_has_been_stopped} seconds'
            f' but stopped at ratio {actual_zoom_ratio}')
        self.expected_zoom_ratio = expected_zoom_ratio
        self.actual_zoom_ratio = actual_zoom_ratio
        self.time_after_zoom_has_been_stopped = time_after_zoom_has_been_stopped


def golden_ratio(min_value: float, max_value: float, inverted: bool = False):
    assert min_value <= max_value, f'{min_value} <= {max_value}'
    # constants of golden ratio are used in the following
    major = 0.618033988749895
    minor = 0.3819660112501051
    if inverted:
        return (min_value * minor) + (max_value * major)
    else:
        return (min_value * major) + (max_value * minor)


class ZoomStepByStepCameraController:
    zoom_speed: ZoomSpeed
    zoom_steps: List[ZoomStep]
    live_view: PanasonicLiveView
    _current_zoom_ratio: Optional[float]

    # noinspection PyShadowingNames
    def __init__(
            self,
            camera_manager: PanasonicCameraManager,
            zoom_steps: List[ZoomStep],
            zoom_speed: ZoomSpeed,
            live_view: PanasonicLiveView):
        self._camera_manager = camera_manager
        self.zoom_steps = zoom_steps
        self.zoom_speed = zoom_speed
        self.live_view = live_view
        self._current_zoom_ratio = None

    def start(self):
        self._current_zoom_ratio = None
        print('waiting for camera connection')
        while self._camera_manager.camera is None:
            sleep(1)
            print('...')
        print('successfully connected to camera')
        print('waiting 3 second for camera to get ready')
        sleep(3)
        # self._camera_manager.camera.zoom_out_fast()
        # return
        print(f"evaluate zoom steps\n")
        self._zoom_step_by_step()

    def _zoom_step_by_step(self):
        is_previous_zoom_step_precalculated = False
        for previous_zoom_step, zoom_step in pairwise(self.zoom_steps):
            if zoom_step.zoom_in_time == 0:
                print(f'skip zoom ratio {zoom_step.zoom_ratio},'
                      f' since it should be reachable in 0 seconds')
                continue
            if zoom_step.stop_zoom_in_time is not None:
                print(f'skip measurement of zoom ratio {zoom_step.zoom_ratio},'
                      f' since (pre-calculated) time is given')
                is_previous_zoom_step_precalculated = True
                continue
            if is_previous_zoom_step_precalculated:
                print(f'zoom to previous zoom ratio {zoom_step.zoom_ratio},'
                      f' since it has been skipped')
                self._zoom_to_step(previous_zoom_step)
                print('')
            self._measure_zoom_step_stop_time(
                zoom_step=zoom_step, previous_zoom_step=previous_zoom_step)
            is_previous_zoom_step_precalculated = False
        print('zoom out fast to reset zoom ratio to 1.0')
        self._camera_manager.camera.zoom_out_fast()

    def _measure_zoom_step_stop_time(
            self,
            zoom_step: ZoomStep,
            previous_zoom_step: ZoomStep):
        wait_step = 0.05
        print(f"measure stop times (min and max)"
              f" of zoom ratio {zoom_step.zoom_ratio}")
        print("=" * 72)
        print(f"check if previous zoom ratio {previous_zoom_step.zoom_ratio}"
              f" is stable")
        self._wait_for_zoom_ratio_to_change_again(previous_zoom_step)
        if self._current_zoom_ratio != previous_zoom_step.zoom_ratio:
            raise Exception(f"previous zoom ratio is unstable or invalid:"
                            f" expected {previous_zoom_step.zoom_ratio},"
                            f" but got {self._current_zoom_ratio}")
        else:
            print(f"previous zoom ratio {previous_zoom_step.zoom_ratio}"
                  f" is stable")
        for time_till_zoom_is_stopped in numpy.arange(zoom_step.zoom_in_time,
                                                      0.0, -wait_step):
            self._zoom_in()
            print(f"zoom ratio {zoom_step.zoom_ratio} is expected to be reached"
                  f" in {zoom_step.zoom_in_time} seconds at the latest")
            print(f"wait {time_till_zoom_is_stopped} seconds")
            sleep(time_till_zoom_is_stopped)
            print('stop zoom')
            self._camera_manager.camera.zoom_stop()
            self._wait_for_zoom_step_to_be_reached(zoom_step)
            if self._current_zoom_ratio == zoom_step.zoom_ratio:
                print(f'reached zoom ratio {zoom_step.zoom_ratio} successfully')
                if zoom_step.max_stop_zoom_in_time is None:
                    print(f'max stop zoom-in time: {time_till_zoom_is_stopped}')
                    zoom_step.max_stop_zoom_in_time = time_till_zoom_is_stopped
                zoom_step.min_stop_zoom_in_time = time_till_zoom_is_stopped
            else:
                print(f'tried to stop zoom at ratio {zoom_step.zoom_ratio},'
                      f" after {time_till_zoom_is_stopped} seconds"
                      f' but stopped at ratio {self._current_zoom_ratio}')
                if (zoom_step.min_stop_zoom_in_time is not None
                        and zoom_step.max_stop_zoom_in_time is not None):
                    break
            self._zoom_back_to(previous_zoom_step)
            print("-" * 72)
        if (zoom_step.min_stop_zoom_in_time is None
                or zoom_step.max_stop_zoom_in_time is None):
            raise Exception(f"Could not determine stop times of zoom ratio"
                            f" {zoom_step.zoom_ratio}")
        print(f'min stop zoom-in time:'
              f' {zoom_step.min_stop_zoom_in_time}')

        self._find_stable_stop_zoom_in_time(zoom_step)
        print('')

    def _zoom_back_to(self, previous_zoom_step):
        last_zoom_to_step_exception = None
        for try_count in range(3):
            try:
                print(f'{"" if try_count == 0 else "retry to "}zoom back'
                      f' to zoom ratio {previous_zoom_step.zoom_ratio}')
                self._zoom_to_step(previous_zoom_step)
            except ZoomToStepException as e:
                last_zoom_to_step_exception = e
                print(f'failed to zoom back to zoom ratio'
                      f' {previous_zoom_step.zoom_ratio} due to error:'
                      f'{traceback.format_exc()}',
                      file=sys.stderr)
                continue
            else:
                break
        else:
            if last_zoom_to_step_exception is not None:
                raise last_zoom_to_step_exception

    def _find_stable_stop_zoom_in_time(self, zoom_step):
        zoom_step.stop_zoom_in_time = golden_ratio(
            zoom_step.min_stop_zoom_in_time, zoom_step.max_stop_zoom_in_time)
        try:
            print(f'use stop zoom-in time (golden ratio):'
                  f' {zoom_step.stop_zoom_in_time}')
            print(f'zoom to zoom ratio {zoom_step.zoom_ratio}'
                  f' to check if measurements are reliable')
            self._zoom_to_step(zoom_step)
        except ZoomToStepException as current_exception:
            def adjust_and_retry(e: ZoomToStepException):
                if e.actual_zoom_ratio < e.expected_zoom_ratio:
                    zoom_step.stop_zoom_in_time = golden_ratio(
                        zoom_step.stop_zoom_in_time,
                        zoom_step.max_stop_zoom_in_time,
                        inverted=True)
                    print(f'adjust stop zoom-in time to'
                          f' {zoom_step.stop_zoom_in_time},'
                          f' since zoom has been stopped too soon previously')
                else:
                    zoom_step.stop_zoom_in_time = golden_ratio(
                        zoom_step.min_stop_zoom_in_time,
                        zoom_step.stop_zoom_in_time)
                    print(f'adjust stop zoom-in time to'
                          f' {zoom_step.stop_zoom_in_time},'
                          f' since zoom has been stopped too late previously')
                print(f'zoom to zoom ratio {zoom_step.zoom_ratio}'
                      f' to check if measurements are reliable')
                self._zoom_to_step(zoom_step)

            for _try in range(3):
                try:
                    adjust_and_retry(current_exception)
                    return
                except ZoomToStepException as adjusted_exception:
                    current_exception = adjusted_exception

            if (current_exception.actual_zoom_ratio
                    > current_exception.expected_zoom_ratio):
                raise current_exception

            extrema = (
                (zoom_step.max_stop_zoom_in_time, 'max_stop_zoom_in_time'),
                (golden_ratio(zoom_step.max_stop_zoom_in_time,
                              zoom_step.zoom_in_time),
                 'golden_ratio(max_stop_zoom_in_time, zoom_in_time)'),
                (golden_ratio(zoom_step.max_stop_zoom_in_time,
                              zoom_step.zoom_in_time,
                              inverted=True),
                 'inverted golden_ratio(max_stop_zoom_in_time, zoom_in_time)'),
                (zoom_step.zoom_in_time, 'zoom_in_time'),
            )
            print('none of the expected stop times worked, try extrema')
            for stop_zoom_in_time, description in extrema:
                try:
                    zoom_step.stop_zoom_in_time = stop_zoom_in_time
                    print(f'try {description} as stop time:'
                          f' {zoom_step.stop_zoom_in_time}')
                    print(f'zoom to zoom ratio {zoom_step.zoom_ratio}'
                          f' to check if measurements are reliable')
                    self._zoom_to_step(zoom_step)
                    return
                except ZoomToStepException as adjusted_exception:
                    current_exception = adjusted_exception
            raise current_exception

    def _wait_for_zoom_step_to_be_reached(self, zoom_step):
        print(f'wait for zoom ratio {zoom_step.zoom_ratio} to be reached')
        start_time = time()
        while (self._current_zoom_ratio is None
               or self._current_zoom_ratio < zoom_step.zoom_ratio):
            self.live_view.image()
            print(f"... current zoom ratio is {self._current_zoom_ratio}")
            elapsed_time = time() - start_time
            if elapsed_time > zoom_step.zoom_in_time * 2:
                print(f'timeout waiting for zoom ratio'
                      f' {zoom_step.zoom_ratio} to be reached')
                break
        if self._current_zoom_ratio == zoom_step.zoom_ratio:
            self._wait_for_zoom_ratio_to_change_again(zoom_step)

    def _wait_for_zoom_ratio_to_change_again(self, zoom_step: ZoomStep):
        time_till_zoom_ratio_is_checked = \
            max(3.0, zoom_step.zoom_in_time * 2)
        print(f'wait {time_till_zoom_ratio_is_checked} seconds'
              f' for zoom ratio to change again')
        sleep(time_till_zoom_ratio_is_checked)
        self.live_view.image()

    # TODO extract to base class shared with ZoomAnalyzerCameraController
    def _zoom_in(self):
        if self.zoom_speed == ZoomSpeed.SLOW:
            print(f"zoom in slow")
            self._camera_manager.camera.zoom_in_slow()
        elif self.zoom_speed == ZoomSpeed.FAST:
            print(f"zoom in fast")
            self._camera_manager.camera.zoom_in_fast()
        else:
            raise Exception(f"unknown zoom speed {self.zoom_speed}")

    def _zoom_out(self):
        if self.zoom_speed == ZoomSpeed.SLOW:
            print(f"zoom out slow")
            self._camera_manager.camera.zoom_out_slow()
        elif self.zoom_speed == ZoomSpeed.FAST:
            print(f"zoom out fast")
            self._camera_manager.camera.zoom_out_fast()
        else:
            raise Exception(f"unknown zoom speed {self.zoom_speed}")

    def on_zoom_ratio(self, zoom_ratio: float):
        self._current_zoom_ratio = zoom_ratio

    def _zoom_to_step(self, zoom_step: ZoomStep):
        self._zoom_out_completely()
        sleep(3)
        if zoom_step.zoom_ratio == 1.0:
            # TODO check if really necessary: it seems that my camera zooms in
            #   faster if motor is still active (zooming out)
            self._wait_for_zoom_step_to_be_reached(zoom_step)
            return
        print(f"_zoom_to_step({zoom_step}),"
              f" where zoom_steps are {self.zoom_steps}")
        time_till_previous_zoom_step_is_reached = sum([
            s.zoom_in_time for s in self.zoom_steps
            if s.zoom_ratio < zoom_step.zoom_ratio])
        time_till_zoom_is_stopped = (zoom_step.stop_zoom_in_time
                                     + time_till_previous_zoom_step_is_reached)
        self._zoom_in()
        print(f"zoom ratio {zoom_step.zoom_ratio} is expected to be reached"
              f" in {time_till_zoom_is_stopped} seconds"
              f" starting from zoom ratio 1.0"
              f" ({time_till_previous_zoom_step_is_reached} seconds till"
              f" previous zoom ratio is reached"
              f" + {zoom_step.stop_zoom_in_time} seconds till zoom ratio"
              f" {zoom_step.zoom_ratio} is reached next")
        sleep(time_till_zoom_is_stopped)
        print('stop zoom')
        self._camera_manager.camera.zoom_stop()
        self._wait_for_zoom_step_to_be_reached(zoom_step)
        if self._current_zoom_ratio == zoom_step.zoom_ratio:
            print(f'reached zoom ratio {zoom_step.zoom_ratio} successfully')
        else:
            raise ZoomToStepException(
                expected_zoom_ratio=zoom_step.zoom_ratio,
                actual_zoom_ratio=self._current_zoom_ratio,
                time_after_zoom_has_been_stopped=time_till_zoom_is_stopped)

    def _zoom_out_completely(self):
        print("zoom out completely")
        self._camera_manager.camera.zoom_out_fast()
        while self._current_zoom_ratio != 1.0:
            self.live_view.image()
            print(f"... current zoom ratio is {self._current_zoom_ratio}")


args = parse_arguments()
configure_logging()
camera_manager = PanasonicCameraManager(
    identify_as=args.identifyToPanasonicCameraAs)

if args.liveView == 'Panasonic':
    live_view = PanasonicLiveView(args.ip, args.port)
    camera_observable = PanasonicCameraObservable(
        min_focal_length=args.cameraMinFocalLength)
    live_view.add_ex_header_listener(camera_observable.on_ex_header)
else:
    print(f"Unsupported live view {args.liveView}")
    exit(1)

# noinspection PyUnboundLocalVariable
zoom_analyzer_camera_controller = ZoomAnalyzerCameraController(
    camera_manager=camera_manager,
    max_zoom_ratio=args.maxZoomRatio,
    zoom_speed=ZoomSpeed.SLOW,
    live_view=live_view)
# noinspection PyUnboundLocalVariable
camera_observable.add_listener(
    ObservableCameraProperty.ZOOM_RATIO,
    zoom_analyzer_camera_controller.on_zoom_ratio)

signal.signal(signal.SIGINT, quit)
signal.signal(signal.SIGTERM, quit)

camera_manager.start()

slow_zoom_steps = None
# @formatter:off
# slow_zoom_steps = [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.9895527362823486), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.9954917430877686, stop_zoom_in_time=2.7791798470253064, min_stop_zoom_in_time=2.64549174308777, max_stop_zoom_in_time=2.9954917430877686, zoom_out_time=0.6975657939910889), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.0021657943725586, stop_zoom_in_time=0.9712640949350639, min_stop_zoom_in_time=0.9521657943725585, max_stop_zoom_in_time=1.0021657943725586, zoom_out_time=0.5132849216461182), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.6973686218261719, stop_zoom_in_time=0.5428601246386981, min_stop_zoom_in_time=0.44736862182617165, max_stop_zoom_in_time=0.6973686218261719, zoom_out_time=0.40135955810546875), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.49675822257995605, stop_zoom_in_time=0.43495482370496663, min_stop_zoom_in_time=0.3967582225799561, max_stop_zoom_in_time=0.49675822257995605, zoom_out_time=0.6865212917327881), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.4023003578186035, stop_zoom_in_time=0.3095952595061193, min_stop_zoom_in_time=0.25230035781860355, max_stop_zoom_in_time=0.4023003578186035, zoom_out_time=0.7116572856903076), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.7013137340545654, stop_zoom_in_time=0.26868994192963863, min_stop_zoom_in_time=0.001313734054564808, max_stop_zoom_in_time=0.7013137340545654, zoom_out_time=0.2968292236328125), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.0131564140319824, stop_zoom_in_time=1.0131564140319824, min_stop_zoom_in_time=0.013156414031981534, max_stop_zoom_in_time=0.3131564140319818, zoom_out_time=0.16654539108276367), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.3901550769805908, stop_zoom_in_time=0.3401550769805909, min_stop_zoom_in_time=0.34015507698059083, max_stop_zoom_in_time=0.34015507698059083, zoom_out_time=0.2217695713043213), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.15993452072143555, stop_zoom_in_time=0.09813112184644605, min_stop_zoom_in_time=0.05993452072143554, max_stop_zoom_in_time=0.15993452072143555, zoom_out_time=0.19324564933776855), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.1768665313720703, stop_zoom_in_time=0.11506313249708085, min_stop_zoom_in_time=0.07686653137207033, max_stop_zoom_in_time=0.1768665313720703, zoom_out_time=0.21143555641174316), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.18616676330566406, stop_zoom_in_time=0.1243633644306746, min_stop_zoom_in_time=0.08616676330566408, max_stop_zoom_in_time=0.18616676330566406, zoom_out_time=0.20763635635375977), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.19944405555725098, stop_zoom_in_time=0.1376406566822615, min_stop_zoom_in_time=0.099444055557251, max_stop_zoom_in_time=0.19944405555725098, zoom_out_time=0.08048605918884277), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.18198490142822266, stop_zoom_in_time=0.15108320199072794, min_stop_zoom_in_time=0.13198490142822267, max_stop_zoom_in_time=0.18198490142822266, zoom_out_time=0)]
# slow_zoom_steps = [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, total_zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=2.0, zoom_in_time=1.1518428325653076, total_zoom_in_time=1.1518428325653076, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.001699686050415, total_zoom_in_time=2.1535425186157227, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.7038912773132324, total_zoom_in_time=2.857433795928955, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.5017242431640625, total_zoom_in_time=3.3591580390930176, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.3963930606842041, total_zoom_in_time=3.7555510997772217, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.706496000289917, total_zoom_in_time=4.462047100067139, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=8.0, zoom_in_time=0.9999425411224365, total_zoom_in_time=5.461989641189575, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.30016255378723145, total_zoom_in_time=5.762152194976807, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.20000767707824707, total_zoom_in_time=5.962159872055054, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.20037317276000977, total_zoom_in_time=6.1625330448150635, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.20260334014892578, total_zoom_in_time=6.365136384963989, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.09929990768432617, total_zoom_in_time=6.464436292648315, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.19851326942443848, total_zoom_in_time=6.662949562072754, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09887242317199707, total_zoom_in_time=6.761821985244751, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None)]
# @formatter:on

# TODO should be calculated by default, but fails in case of my camera most
#   of the time due to AssertionError:
#     could not find ZoomStep of zoom ratio 9.0 when zooming out from 10.0
fast_zoom_steps = []
# fast_zoom_steps = None


def analyze_zoom_steps(zoom_speed: ZoomSpeed):
    global zoom_analyzer_camera_controller, live_view
    zoom_analyzer_camera_controller.zoom_speed = zoom_speed
    zoom_analyzer_camera_controller.start()
    while not zoom_analyzer_camera_controller.is_stopped():
        # noinspection PyUnboundLocalVariable
        live_view.image()  # read zoom ratio
    return zoom_analyzer_camera_controller.zoom_steps


def update_total_zoom_in_time(zoom_steps: List[ZoomStep]):
    previous_step = None
    for step in zoom_steps:
        step.total_zoom_in_time = (
            0 if previous_step is None
            else previous_step.total_zoom_in_time + step.zoom_in_time)
        previous_step = step


def optimize_sampled_zoom_steps(multiple_zoom_steps: List[List[ZoomStep]]):
    # TODO optimize zoom out time
    print('\n')
    for steps in zip(*multiple_zoom_steps):
        print(f'{steps[0].zoom_ratio:4}\t||\t'
              + '\t'.join(
            map(lambda s: f'{float(s.zoom_in_time):5.3f}', steps)))
    for steps in multiple_zoom_steps:
        update_total_zoom_in_time(steps)
    print('\n')
    run_columns = len(multiple_zoom_steps)
    print(f'  Runs -->\t||\t'
          + '\t\t'.join(f'Run {i + 1}'.center(23) for i in range(run_columns))
          + '\t\t||\t' + 'Minima'.center(23)
          + '\t\t||\t' + 'Optimized Step Time'.center(21))
    print(f'zoom ratio\t||\t'
          + ('step time\ttotal time\t\t' * run_columns)
          + '||\tstep time\ttotal time\t\t'
          + '||\t' + '= min total time diff')
    print(f'----------\t||\t'
          + ('---------\t----------\t\t' * run_columns)
          + '||\t----------\t----------\t\t||\t' + ('-' * 21))
    optimized_zoom_steps = []
    previous_total_zoom_in_time = None
    for steps in zip(*multiple_zoom_steps):
        zoom_ratio = steps[0].zoom_ratio
        min_total_zoom_in_time = min(map(lambda s: float(s.total_zoom_in_time),
                                         steps))
        optimized_zoom_in_time = (
            0 if previous_total_zoom_in_time is None
            else min_total_zoom_in_time - previous_total_zoom_in_time)
        optimized_zoom_steps.append(
            ZoomStep(zoom_ratio=zoom_ratio,
                     zoom_in_time=optimized_zoom_in_time))
        print(f'{zoom_ratio :10}\t||\t'
              + '\t\t'.join(map(lambda s: f'{float(s.zoom_in_time):9.3f}\t'
                                          f'{float(s.total_zoom_in_time):10.3f}',
                                steps))
              + '\t\t||\t'
              + f'{min(map(lambda s: float(s.zoom_in_time), steps)):10.3f}'
              + f'\t{min_total_zoom_in_time:10.3f}'
              + '\t\t||\t'
              + f'{optimized_zoom_in_time:21.3f}')
        previous_total_zoom_in_time = min_total_zoom_in_time
    print('\n' * 2)
    update_total_zoom_in_time(optimized_zoom_steps)
    return optimized_zoom_steps


def sample_zoom_steps(
        zoom_speed: ZoomSpeed,
        sample_size: int = 9,
        max_retry_count: int = 10):
    multi_slow_zoom_steps = []
    max_length = 0
    retry_count = 0
    while len(multi_slow_zoom_steps) < sample_size:
        print('-' * 40)
        print(f'sample {len(multi_slow_zoom_steps) + 1} of {sample_size}'
              f' with zoom step count of {max_length or "unknown"}')
        print('-' * 40)
        # noinspection PyBroadException
        try:
            steps = analyze_zoom_steps(zoom_speed)
            steps_length = len(steps)
            if steps_length > max_length:
                if max_length != 0:
                    print(f'reset samples, since higher zoom step count of'
                          f' {steps_length} has been found')
                multi_slow_zoom_steps = [steps]
                max_length = steps_length
                retry_count = 0
            elif steps_length == max_length:
                print(f'finished and added current sample')
                multi_slow_zoom_steps.append(steps)
                retry_count = 0
            else:
                retry_count += 1
                print(f'ignore current sample and retry,'
                      f' since not all zoom steps have been captured:'
                      f' only {steps_length} of {max_length}')
        except Exception:
            print(f'failed to sample zoom steps due to error:'
                  f' {traceback.format_exc()}',
                  file=sys.stderr)
            # noinspection PyBroadException
            try:
                zoom_analyzer_camera_controller.cancel()
                print('wait for camera to get ready')
                sleep(3)
            except Exception:
                print(f'failed to cancel zoom analyzer: {traceback.format_exc()}',
                      file=sys.stderr)
                quit(1)
            retry_count += 1
            if retry_count <= max_retry_count:
                print('try to sample zoom steps again')
        if retry_count > max_retry_count:
            print('maximum retry count reached,'
                  ' while trying to sample zoom steps',
                  file=sys.stderr)
            quit(1)
        print('\n' * 2)
    print(f'multi_slow_zoom_steps: {multi_slow_zoom_steps}')
    print(f'max_length: {max_length}')
    print(len(multi_slow_zoom_steps))
    print(list(map(len, multi_slow_zoom_steps)))
    return multi_slow_zoom_steps


def print_zoom_steps_as_tsv(zoom_steps: List[ZoomStep]):
    columns = (
        'zoom_ratio',
        'zoom_in_time',
        'total_zoom_in_time',
        'stop_zoom_in_time',
        'min_stop_zoom_in_time',
        'max_stop_zoom_in_time',
        'zoom_out_time',
    )
    print('\t'.join(columns))
    for s in zoom_steps:
        print('\t'.join(map(lambda prop: str(getattr(s, prop)), columns)))


# noinspection PyBroadException
try:
    if slow_zoom_steps is None:
        print('=' * 33)
        print(f'sample zoom steps with slow speed')
        print('=' * 33)
        multi_slow_zoom_steps = sample_zoom_steps(ZoomSpeed.SLOW)
        # TODO remove uncommented precalculated values of multi_slow_zoom_steps
        # @formatter:off
        # multi_slow_zoom_steps = [[ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=1.0067009925842285), ZoomStep(zoom_ratio=2.0, zoom_in_time=3.1767921447753906, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7013933658599854), ZoomStep(zoom_ratio=3.0, zoom_in_time=0.818373441696167, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.47425389289855957), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.5958828926086426, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.4318220615386963), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.6024904251098633, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5838179588317871), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.3976614475250244, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5738935470581055), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.6164145469665527, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5438327789306641), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.0917303562164307, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.0694894790649414), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.30113840103149414, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3301973342895508), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.20016121864318848, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.1984236240386963), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.20527148246765137, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.2001481056213379), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.2945592403411865, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19804596900939941), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.011595010757446289, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.07778429985046387), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.19402265548706055, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09566831588745117, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.9592199325561523), ZoomStep(zoom_ratio=2.0, zoom_in_time=3.0019898414611816, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7418229579925537), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.0198304653167725, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.49592018127441406), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.5654041767120361, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.40183258056640625), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.6267201900482178, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.39429283142089844), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.2550938129425049, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.8580029010772705), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.7067039012908936, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.4587423801422119), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.0952587127685547, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19881987571716309), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.3007984161376953, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19782662391662598), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.21933579444885254, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19257736206054688), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.1894087791442871, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20192646980285645), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.34815120697021484, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.03720593452453613), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.0008149147033691406, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.24931025505065918), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.15492725372314453, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09551572799682617, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.9722003936767578), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.898146152496338, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7016146183013916), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.1725003719329834, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5037057399749756), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.5667688846588135, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.40355443954467773), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.4904603958129883, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6965839862823486), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.40337228775024414, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7013366222381592), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.6984100341796875, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.2919130325317383), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.0025978088378906, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.1965022087097168), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.30362868309020996, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20021510124206543), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.19995760917663574, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.10104727745056152), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.19875741004943848, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.30414485931396484), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.19971990585327148, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19880175590515137), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.10181760787963867, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.08654642105102539), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.20155048370361328, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.10191583633422852, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)]]
        # multi_slow_zoom_steps = [[ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=1.1444997787475586), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.985262393951416, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.49442052841186523), ZoomStep(zoom_ratio=3.0, zoom_in_time=0.9913039207458496, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7155766487121582), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.693007230758667, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3874638080596924), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.4997975826263428, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.713566780090332), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.4029664993286133, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6992356777191162), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.709263801574707, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.29436755180358887), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.0008037090301514, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.2076399326324463), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.2930011749267578, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20254945755004883), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.19976544380187988, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.1997082233428955), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.20673274993896484, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.18357610702514648), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.19692158699035645, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.007399082183837891), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.10475778579711914, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.2776632308959961), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.20498061180114746, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09458446502685547, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.8198115825653076), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.969595432281494, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.888507604598999), ZoomStep(zoom_ratio=3.0, zoom_in_time=0.9902341365814209, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5004723072052002), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.6970987319946289, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.39942288398742676), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.5038983821868896, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7015388011932373), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.40816807746887207, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6962687969207764), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.7036471366882324, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.30986762046813965), ZoomStep(zoom_ratio=8.0, zoom_in_time=0.9967741966247559, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.09753751754760742), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.35964345932006836, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.15941572189331055), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.14204931259155273, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3426511287689209), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.19951939582824707, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19835352897644043), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.20115447044372559, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20021581649780273), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.09356403350830078, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.0833442211151123), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.20600128173828125, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09720063209533691, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.9786853790283203), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.9767754077911377, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6647448539733887), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.003103494644165, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5409650802612305), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.7057147026062012, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3944973945617676), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.49475550651550293, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7028887271881104), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.39885973930358887, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7062954902648926), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.7104001045227051, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.29884791374206543), ZoomStep(zoom_ratio=8.0, zoom_in_time=0.9980161190032959, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.18562698364257812), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.3053100109100342, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20552802085876465), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.19484162330627441, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.1979970932006836), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.19875478744506836, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19792532920837402), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.19829845428466797, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20525312423706055), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.11756134033203125, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.0906517505645752), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.18875527381896973, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09801602363586426, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=1.1459929943084717), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.823500394821167, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5928418636322021), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.0622138977050781, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6022958755493164), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.638343095779419, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.2264540195465088), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.4987514019012451, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.8812477588653564), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.3996083736419678, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6982040405273438), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.8753941059112549, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.15776896476745605), ZoomStep(zoom_ratio=8.0, zoom_in_time=0.8595402240753174, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.34890127182006836), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.3310544490814209, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20245027542114258), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.14770150184631348, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19786286354064941), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.20540070533752441, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.061453819274902344), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.19363021850585938, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.334209680557251), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.09578442573547363, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.09155893325805664), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.2041490077972412, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.0951683521270752, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6624546051025391), ZoomStep(zoom_ratio=2.0, zoom_in_time=3.011552095413208, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=1.0190858840942383), ZoomStep(zoom_ratio=3.0, zoom_in_time=0.9865438938140869, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.500302791595459), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.5960211753845215, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3884444236755371), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.6102235317230225, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7090754508972168), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.39017653465270996, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.70497727394104), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.704911470413208, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.2638869285583496), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.0076193809509277, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.22968196868896484), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.29367852210998535, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20855212211608887), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.20090007781982422, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19100022315979004), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.23405170440673828, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.1959059238433838), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.36155033111572266, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20559978485107422), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.0008523464202880859, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.08318662643432617), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.11423063278198242, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.0982811450958252, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=1.0362517833709717), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.892042875289917, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7057077884674072), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.0807340145111084, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5051560401916504), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.7128236293792725, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3895242214202881), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.47566747665405273, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7026596069335938), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.4069225788116455, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7072663307189941), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.6046299934387207, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.29995083808898926), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.1078801155090332, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20332789421081543), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.29493284225463867, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.2000267505645752), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.1946876049041748, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19803094863891602), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.20168733596801758, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19668078422546387), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.21226978302001953, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19116902351379395), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.0964052677154541, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.08922028541564941), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.1956615447998047, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09973907470703125, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.9950017929077148), ZoomStep(zoom_ratio=2.0, zoom_in_time=3.002467393875122, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5438101291656494), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.0628769397735596, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6640853881835938), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.6050381660461426, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3344876766204834), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.5982105731964111, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7576355934143066), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.4121739864349365, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7104940414428711), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.5979952812194824, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3021085262298584), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.0966429710388184, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19406938552856445), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.31005120277404785, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20619606971740723), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.19205474853515625, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20052576065063477), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.19811797142028809, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20034170150756836), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.19588303565979004, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.1982893943786621), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.0975961685180664, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.08274459838867188), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.20408892631530762, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09848976135253906, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=1.2628633975982666), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.92985463142395, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6007614135742188), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.1208205223083496, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6060535907745361), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.5839636325836182, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.23065805435180664), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.5035707950592041, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.8628792762756348), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.39850950241088867, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.7098724842071533), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.7681033611297607, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.30176472663879395), ZoomStep(zoom_ratio=8.0, zoom_in_time=0.9311027526855469, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20111942291259766), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.30910348892211914, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19797897338867188), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.19600510597229004, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19820523262023926), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.19925546646118164, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.08725428581237793), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.20120477676391602, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.3104422092437744), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.10945630073547363, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.07606673240661621), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.19739103317260742, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.10010099411010742, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)], [ZoomStep(zoom_ratio=1.0, zoom_in_time=0, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.9964935779571533), ZoomStep(zoom_ratio=2.0, zoom_in_time=2.901379346847534, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.5937762260437012), ZoomStep(zoom_ratio=3.0, zoom_in_time=1.0737237930297852, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6159868240356445), ZoomStep(zoom_ratio=4.0, zoom_in_time=0.658966064453125, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.4022507667541504), ZoomStep(zoom_ratio=5.0, zoom_in_time=0.5302305221557617, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.6780710220336914), ZoomStep(zoom_ratio=6.0, zoom_in_time=0.5949413776397705, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.724625825881958), ZoomStep(zoom_ratio=7.1, zoom_in_time=0.4147529602050781, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.29571104049682617), ZoomStep(zoom_ratio=8.0, zoom_in_time=1.0870628356933594, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20589232444763184), ZoomStep(zoom_ratio=9.0, zoom_in_time=0.3040742874145508, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20006442070007324), ZoomStep(zoom_ratio=10.0, zoom_in_time=0.2089989185333252, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.20096969604492188), ZoomStep(zoom_ratio=11.0, zoom_in_time=0.19275856018066406, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19396400451660156), ZoomStep(zoom_ratio=12.0, zoom_in_time=0.21896100044250488, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.19588494300842285), ZoomStep(zoom_ratio=13.0, zoom_in_time=0.08687281608581543, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0.08037018775939941), ZoomStep(zoom_ratio=14.0, zoom_in_time=0.20806241035461426, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=None), ZoomStep(zoom_ratio=14.3, zoom_in_time=0.09647417068481445, stop_zoom_in_time=None, min_stop_zoom_in_time=None, max_stop_zoom_in_time=None, zoom_out_time=0)]]
        # @formatter:on
        slow_zoom_steps = optimize_sampled_zoom_steps(multi_slow_zoom_steps)
        print(f'slow_zoom_steps: {slow_zoom_steps}')
        print('\nfinished sampling zoom steps with slow speed')
        print('\n' * 2)

    print('\n')
    print_zoom_steps_as_tsv(slow_zoom_steps)
    print('\n')

    if fast_zoom_steps is None:
        print('=' * 33)
        print(f'sample zoom steps with fast speed')
        print('=' * 33)
        fast_zoom_steps = optimize_sampled_zoom_steps(
            sample_zoom_steps(ZoomSpeed.FAST))
        print(f'fast_zoom_steps: {fast_zoom_steps}')
        print('\nfinished sampling zoom steps with fast speed')
        print('\n' * 2)

    # TODO remove uncommented precalculated values of slow_zoom_steps
    # slow_zoom_steps = [
    #     ZoomStep(zoom_ratio=1.0, stop_zoom_in_time=0, zoom_in_time=0,
    #              zoom_out_time=1.0003037452697754),
    #     ZoomStep(zoom_ratio=2.0, stop_zoom_in_time=0,
    #              zoom_in_time=2.9514217376708984,
    #              zoom_out_time=0.7093634605407715),
    #     ZoomStep(zoom_ratio=3.0, stop_zoom_in_time=0,
    #              zoom_in_time=1.0997443199157715,
    #              zoom_out_time=0.4926338195800781),
    #     ZoomStep(zoom_ratio=4.0, stop_zoom_in_time=0,
    #              zoom_in_time=0.6136748790740967,
    #              zoom_out_time=0.4096393585205078),
    #     ZoomStep(zoom_ratio=5.0, stop_zoom_in_time=0,
    #              zoom_in_time=0.4909799098968506,
    #              zoom_out_time=0.6945595741271973),
    #     ZoomStep(zoom_ratio=6.0,
    #              stop_zoom_in_time=0, zoom_in_time=0.40047478675842285,
    #              zoom_out_time=0.7033517360687256),
    #     ZoomStep(zoom_ratio=7.1, stop_zoom_in_time=0,
    #              zoom_in_time=0.7125728130340576,
    #              zoom_out_time=0.2920267581939697),
    #     ZoomStep(zoom_ratio=8.0, stop_zoom_in_time=0,
    #              zoom_in_time=0.9895591735839844,
    #              zoom_out_time=0.19847440719604492),
    #     ZoomStep(zoom_ratio=9.0,
    #              stop_zoom_in_time=0, zoom_in_time=0.40214109420776367,
    #              zoom_out_time=0.20867395401000977),
    #     ZoomStep(zoom_ratio=10.0,
    #              stop_zoom_in_time=0, zoom_in_time=0.10116839408874512,
    #              zoom_out_time=0.19977283477783203),
    #     ZoomStep(zoom_ratio=11.0,
    #              stop_zoom_in_time=0, zoom_in_time=0.2007291316986084,
    #              zoom_out_time=0.20025086402893066),
    #     ZoomStep(zoom_ratio=12.0,
    #              stop_zoom_in_time=0, zoom_in_time=0.20136809349060059,
    #              zoom_out_time=0.19693303108215332),
    #     ZoomStep(zoom_ratio=13.0,
    #              stop_zoom_in_time=0, zoom_in_time=0.19879579544067383,
    #              zoom_out_time=0.09151411056518555),
    #     ZoomStep(zoom_ratio=14.3,
    #              stop_zoom_in_time=0, zoom_in_time=0.19693827629089355,
    #              zoom_out_time=0)]

    # noinspection PyUnboundLocalVariable
    zoom_step_by_step_camera_controller = ZoomStepByStepCameraController(
        camera_manager=camera_manager,
        zoom_steps=slow_zoom_steps,
        zoom_speed=ZoomSpeed.SLOW,
        live_view=live_view)
    # noinspection PyUnboundLocalVariable
    camera_observable.add_listener(
        ObservableCameraProperty.ZOOM_RATIO,
        zoom_step_by_step_camera_controller.on_zoom_ratio)
    zoom_step_by_step_camera_controller.start()

    if args.output is not None:
        args.output.write_text(
            json.dumps(
                {
                    'slow': slow_zoom_steps,
                    'fast': fast_zoom_steps,
                },
                cls=ZoomStepJsonEncoder,
                indent=2))
except Exception:
    # noinspection PyBroadException
    try:
        print(f'\n\ntry to zoom out camera (completely)')
        camera_manager.camera.zoom_out_fast()
    except Exception:
        print(f'failed to zoom out camera: {traceback.format_exc()}',
              file=sys.stderr)
    print(f'analysis failed: {traceback.format_exc()}',
          file=sys.stderr)
    quit(1)
quit()
