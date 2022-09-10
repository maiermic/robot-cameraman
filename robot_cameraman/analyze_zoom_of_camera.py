import argparse
import json
import logging
import signal
import threading
import traceback
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

# noinspection Mypy
import numpy
import sys
from time import time, sleep
from more_itertools import first_true, pairwise
from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from robot_cameraman.camera_controller import ElapsedTime
from robot_cameraman.camera_observable import \
    PanasonicCameraObservable, ObservableCameraProperty
from robot_cameraman.live_view import PanasonicLiveView


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


@dataclass()
class ZoomStep:
    zoom_ratio: float
    zoom_in_time: float
    stop_zoom_in_time: Optional[float]
    min_stop_zoom_in_time: Optional[float]
    max_stop_zoom_in_time: Optional[float]
    zoom_out_time: Optional[float]

    def __init__(
            self,
            zoom_ratio: float,
            zoom_in_time: float,
            stop_zoom_in_time: Optional[float] = None,
            min_stop_zoom_in_time: Optional[float] = None,
            max_stop_zoom_in_time: Optional[float] = None,
            zoom_out_time: Optional[float] = None) -> None:
        self.zoom_ratio = zoom_ratio
        self.zoom_in_time = zoom_in_time
        self.stop_zoom_in_time = stop_zoom_in_time
        self.min_stop_zoom_in_time = min_stop_zoom_in_time
        self.max_stop_zoom_in_time = max_stop_zoom_in_time
        self.zoom_out_time = zoom_out_time


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

    zoom_speed: ZoomSpeed
    _state: _State
    _camera_manager: PanasonicCameraManager
    _max_zoom_ratio: float
    _previous_zoom_ratio: Optional[float]
    zoom_steps: List[ZoomStep]

    # noinspection PyShadowingNames
    def __init__(
            self,
            camera_manager: PanasonicCameraManager,
            max_zoom_ratio: float,
            zoom_speed: ZoomSpeed):
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
        print('waiting for camera connection')
        while self._camera_manager.camera is None:
            sleep(1)
            print('...')
        print('successfully connected to camera')
        print('waiting 3 second for camera to get ready')
        sleep(3)
        print(f"start analysis")
        self._zoom_in()
        self._elapsed_time.reset()

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
        if self._state == self._State.STOPPED:
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
            print(zoom_ratio)
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
        print(zoom_ratio)
        zoom_step = self._get_zoom_step_of_ratio(zoom_ratio)
        assert zoom_step is not None, (
            f"could not find ZoomStep of zoom ratio {zoom_ratio}"
            f" when zooming out from {self._previous_zoom_ratio}")
        zoom_step.zoom_out_time = self._elapsed_time.update()

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
            print(f'zoom back to zoom ratio'
                  f' {previous_zoom_step.zoom_ratio}')
            self._zoom_to_step(previous_zoom_step)
            print("-" * 72)
        if (zoom_step.min_stop_zoom_in_time is None
                or zoom_step.max_stop_zoom_in_time is None):
            raise Exception(f"Could not determine stop times of zoom ratio"
                            f" {zoom_step.zoom_ratio}")
        print(f'min stop zoom-in time:'
              f' {zoom_step.min_stop_zoom_in_time}')

        self._find_stable_stop_zoom_in_time(zoom_step)
        print('')

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
zoom_analyzer_camera_controller = ZoomAnalyzerCameraController(
    camera_manager=camera_manager,
    max_zoom_ratio=args.maxZoomRatio,
    zoom_speed=ZoomSpeed.SLOW)

if args.liveView == 'Panasonic':
    live_view = PanasonicLiveView(args.ip, args.port)
    camera_observable = PanasonicCameraObservable(
        min_focal_length=args.cameraMinFocalLength)
    live_view.add_ex_header_listener(camera_observable.on_ex_header)
    camera_observable.add_listener(
        ObservableCameraProperty.ZOOM_RATIO,
        zoom_analyzer_camera_controller.on_zoom_ratio)
else:
    print(f"Unsupported live view {args.liveView}")
    exit(1)

signal.signal(signal.SIGINT, quit)
signal.signal(signal.SIGTERM, quit)

camera_manager.start()


def analyze_zoom_steps(zoom_speed: ZoomSpeed):
    global zoom_analyzer_camera_controller, live_view
    zoom_analyzer_camera_controller.zoom_speed = zoom_speed
    zoom_analyzer_camera_controller.start()
    while not zoom_analyzer_camera_controller.is_stopped():
        # noinspection PyUnboundLocalVariable
        live_view.image()  # read zoom ratio
    return zoom_analyzer_camera_controller.zoom_steps

# noinspection PyBroadException
try:
    slow_zoom_steps = analyze_zoom_steps(ZoomSpeed.SLOW)
    print(slow_zoom_steps)

    fast_zoom_steps = analyze_zoom_steps(ZoomSpeed.FAST)
    print(fast_zoom_steps)

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
