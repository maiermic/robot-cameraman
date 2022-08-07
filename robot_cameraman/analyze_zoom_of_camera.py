import argparse
import json
import logging
import signal
import threading
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

# noinspection Mypy
import time
from more_itertools import first_true
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


def quit(sig=None, frame=None):
    global camera_manager
    print("Exiting...")
    if threading.current_thread() != camera_manager:
        print('wait for camera manager thread')
        camera_manager.cancel()
        camera_manager.join()
    exit(0)


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
    zoom_out_time: float


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
            time.sleep(1)
            print('...')
        print('successfully connected to camera')
        print('waiting 3 second for camera to get ready')
        time.sleep(3)
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
        if self._state == self._State.ZOOM_OUT:
            if zoom_ratio == 1:
                self._state = self._State.STOPPED
                self.update_zoom_out_time(zoom_ratio)
        elif self._previous_zoom_ratio != zoom_ratio:
            zoom_in_time = 0 if zoom_ratio == 1 else self._elapsed_time.update()
            self.zoom_steps.append(
                ZoomStep(zoom_ratio=zoom_ratio,
                         zoom_in_time=zoom_in_time,
                         zoom_out_time=0))
            print(zoom_ratio)
        if zoom_ratio == self._max_zoom_ratio:
            self._zoom_out()
            self._state = self._State.ZOOM_OUT
            self._elapsed_time.reset()
        elif (self._state == self._State.ZOOM_OUT
              and self._previous_zoom_ratio != zoom_ratio):
            self.update_zoom_out_time(zoom_ratio)
        self._previous_zoom_ratio = zoom_ratio
        # TODO analyze with zoom in fast

    def update_zoom_out_time(self, zoom_ratio):
        print(zoom_ratio)
        zoom_step = self._get_zoom_step_of_ratio(zoom_ratio)
        assert zoom_step is not None, (
            f"could not find ZoomStep of zoom ratio {zoom_ratio}"
            f"when zooming out from {self._previous_zoom_ratio}")
        zoom_step.zoom_out_time = self._elapsed_time.update()

    def _get_zoom_step_of_ratio(self, zoom_ratio: float):
        return first_true(
            self.zoom_steps,
            None,
            lambda zoom_step: zoom_step.zoom_ratio == zoom_ratio)


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

try:
    zoom_analyzer_camera_controller.start()
    while not zoom_analyzer_camera_controller.is_stopped():
        # noinspection PyUnboundLocalVariable
        image = live_view.image()
    slow_zoom_steps = zoom_analyzer_camera_controller.zoom_steps
    print(slow_zoom_steps)
    zoom_analyzer_camera_controller.zoom_speed = ZoomSpeed.FAST
    zoom_analyzer_camera_controller.start()
    while not zoom_analyzer_camera_controller.is_stopped():
        # noinspection PyUnboundLocalVariable
        image = live_view.image()
    fast_zoom_steps = zoom_analyzer_camera_controller.zoom_steps
    print(fast_zoom_steps)
    if args.output is not None:
        args.output.write_text(
            json.dumps(
                {
                    'slow': slow_zoom_steps,
                    'fast': fast_zoom_steps,
                },
                cls=ZoomStepJsonEncoder,
                indent=2))
finally:
    quit()
