import argparse
import logging
import signal
import threading
from enum import Enum, auto
from pathlib import Path
from typing import List

# noinspection Mypy
import time
from typing_extensions import Protocol

from panasonic_camera.camera import PanasonicCamera
from panasonic_camera.camera_manager import PanasonicCameraManager
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


class ZoomAnalyzerCameraController:
    class _State(Enum):
        ANALYZE_SLOW = auto()
        ZOOM_OUT = auto()
        STOPPED = auto()

    _state: _State
    _camera_manager: PanasonicCameraManager
    _max_zoom_ratio: float
    zoom_ratios: List[float]

    # noinspection PyShadowingNames
    def __init__(
            self,
            camera_manager: PanasonicCameraManager,
            max_zoom_ratio: float):
        self._max_zoom_ratio = max_zoom_ratio
        self._state = self._State.STOPPED
        self._camera_manager = camera_manager
        self.zoom_ratios = []

    def start(self):
        assert self._state == self._State.STOPPED
        assert not self.zoom_ratios
        self._state = self._State.ANALYZE_SLOW
        print('waiting for camera connection')
        while self._camera_manager.camera is None:
            time.sleep(1)
            print('...')
        print('successfully connected to camera')
        print('start analysis with slow zoom speed')
        # noinspection PyTypeChecker
        camera: PanasonicCamera = self._camera_manager.camera
        camera.zoom_in_slow()

    def is_stopped(self):
        return self._state == self._State.STOPPED

    def on_zoom_ratio(self, zoom_ratio: float):
        if self._state == self._State.ZOOM_OUT:
            if zoom_ratio == 1:
                self._state = self._State.STOPPED
        elif not self.zoom_ratios or self.zoom_ratios[-1] != zoom_ratio:
            self.zoom_ratios.append(zoom_ratio)
            print(zoom_ratio)
        if zoom_ratio == self._max_zoom_ratio:
            print('zoom out')
            self._camera_manager.camera.zoom_out_fast()
            self._state = self._State.ZOOM_OUT
        # TODO analyze with zoom in fast


args = parse_arguments()
configure_logging()
camera_manager = PanasonicCameraManager(
    identify_as=args.identifyToPanasonicCameraAs)
zoom_analyzer_camera_controller = ZoomAnalyzerCameraController(
    camera_manager=camera_manager,
    max_zoom_ratio=args.maxZoomRatio)

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
    # TODO write result (zoom_analyzer_camera_controller.zoom_ratios)
    #  to args.output
finally:
    quit()
