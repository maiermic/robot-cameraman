import argparse
import logging
import signal
import threading
# noinspection Mypy
from pathlib import Path
from typing import Optional

import PIL.Image
import PIL.ImageFont
import cv2
from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from robot_cameraman.annotation import ImageAnnotator
from robot_cameraman.camera_controller import SmoothCameraController, \
    SpeedManager, CameraAngleLimitController, \
    PredictiveCameraZoomRatioLimitController, CameraZoomRatioLimitController, \
    CameraZoomIndexLimitController
from robot_cameraman.camera_observable import PanasonicCameraObservable
from robot_cameraman.camera_speeds import ZoomSpeed, CameraSpeeds
from robot_cameraman.cameraman import Cameraman
from robot_cameraman.cameraman_mode_manager import CameramanModeManager
from robot_cameraman.configuration import read_configuration_file
from robot_cameraman.detection_engine.color import ColorDetectionEngine, \
    ColorDetectionEngineUI
from robot_cameraman.events import EventEmitter, Event
from robot_cameraman.gimbal import DummyGimbal, TiltInvertedGimbal, \
    create_simple_bgc_gimbal
from robot_cameraman.image_detection import DummyDetectionEngine, \
    EdgeTpuDetectionEngine
from robot_cameraman.live_view import WebcamLiveView, PanasonicLiveView, \
    ImageSize, DummyLiveView, FileLiveView
from robot_cameraman.max_speed_and_acceleration_updater import \
    MaxSpeedAndAccelerationUpdater
from robot_cameraman.object_tracking import ObjectTracker
from robot_cameraman.resource import read_label_file
from robot_cameraman.server import run_server, ImageContainer
from robot_cameraman.tracking import Destination, StopIfLostTrackingStrategy, \
    RotateSearchTargetStrategy, ConfigurableTrackingStrategy, \
    ConfigurableAlignTrackingStrategy, ConfigurableTrackingStrategyUi, \
    StaticSearchTargetStrategy
from robot_cameraman.ui import StatusBar, open_file_dialog
from robot_cameraman.updatable_configuration import UpdatableConfiguration
from robot_cameraman.zoom import parse_zoom_steps, parse_zoom_ratio_index_ranges

to_exit: threading.Event
server_image: ImageContainer


def create_video_writer(output_file: Path, image_size: ImageSize):
    return cv2.VideoWriter(
        str(output_file),
        cv2.VideoWriter_fourcc(*'MJPG'),
        15,
        image_size)


def create_angle_limit_controller(
        event_emitter: EventEmitter) -> CameraAngleLimitController:
    controller = CameraAngleLimitController()
    event_emitter.add_listener(Event.ANGLES,
                               controller.update_current_angles)
    return controller


class RobotCameramanArguments(Protocol):
    config: Path
    detectionEngine: str
    model: Path
    labels: Path
    maxObjects: int
    confidence: float
    gimbal: str
    gimbalTiltInverted: bool
    liveView: str
    ip: str
    port: int
    identifyToPanasonicCameraAs: str
    targetLabelId: int
    output: Path
    font: Path
    fontSize: int
    debug: bool
    search_strategy: str
    rotatingSearchSpeed: int
    rotationalAccelerationPerSecond: int
    tiltingAccelerationPerSecond: int
    variance: int
    liveViewWith: int
    liveViewHeight: int
    cameraMinFocalLength: float
    cameraMaxFocalLength: float
    camera_zoom_steps: Optional[Path]
    camera_zoom_ratio_index_ranges: Optional[Path]
    ssl_key: Path
    ssl_certificate: Path


def parse_arguments() -> RobotCameramanArguments:
    resources: Path = Path(__file__).parent / 'resources'
    mobilenet = 'mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite'
    parser = argparse.ArgumentParser(
        description="Detect objects in a video file using Google Coral USB.")
    parser.add_argument(
        '--config',
        type=Path,
        default=Path(__file__).parent.parent / '.robot-cameraman.config.json',
        help="Path to the JSON file that is used to load"
             "and store the configuration.")
    parser.add_argument('--detectionEngine', type=str,
                        default='EdgeTPU',
                        help="The detection engine to use."
                             " Either 'EdgeTPU' (Google Coral),"
                             " 'Color' or 'Dummy'")
    parser.add_argument(
        '--model',
        type=Path,
        default=resources / mobilenet,
        help="Path to the neural network graph file.")
    parser.add_argument(
        '--labels',
        type=Path,
        default=resources / 'coco_labels.txt',
        help="Path to labels file.")
    parser.add_argument('--maxObjects', type=int,
                        default=10,
                        help="Maximum objects to infer in each frame of video.")
    parser.add_argument('--confidence', type=float,
                        default=0.50,
                        help="Minimum confidence threshold to tag objects.")
    parser.add_argument('--gimbal', type=str,
                        default='SimpleBGC',
                        help="The gimbal to use. Either 'SimpleBGC' or 'Dummy'")
    parser.add_argument(
        '--gimbalTiltInverted',
        action='store_true',
        help="Invert tilting direction of gimbal."
             " Should be used if the camera is mounted on the gimbal in the"
             " opposite direction (rotated 180 degree),"
             " the tilt speed and angle has to be inverted.")
    parser.add_argument('--liveView', type=str,
                        default='Panasonic',
                        help="The live view (camera) to use."
                             "Either 'Panasonic', 'Webcam' or 'Dummy'")
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
    parser.add_argument('--targetLabelId', type=int,
                        default=0,
                        help="ID of label to track.")
    parser.add_argument('--output',
                        type=Path,
                        default=None,
                        help="Video output file of annotated image stream.")
    parser.add_argument('--font',
                        type=Path,
                        default=resources / 'Roboto-Regular.ttf',
                        help="Font used in image annotations.")
    parser.add_argument('--fontSize',
                        type=int,
                        default=30,
                        help="Font size used in image annotations.")
    parser.add_argument('--debug',
                        action='store_true',
                        help="Enable debug logging")
    parser.add_argument('--search-strategy',
                        type=str, default='rotate',
                        help="If target is lost,"
                             " the camera searches for a new target."
                             " If the strategy 'rotate' (default) is used,"
                             " the gimbal pans clockwise at constant speed"
                             " (given by argument --rotatingSearchSpeed)."
                             " If the strategy 'static' is used,"
                             " the gimbal moves (pans, tilts and zooms)"
                             " with constant speed"
                             " (given by argument --rotatingSearchSpeed)"
                             " to a certain position"
                             " (can be configured in the web UI).")
    parser.add_argument('--rotatingSearchSpeed',
                        type=int, default=0,
                        help="If target is lost, search for new target by"
                             " rotating at the given speed")
    parser.add_argument('--rotationalAccelerationPerSecond',
                        type=int, default=400,
                        help="Defines how fast the gimbal may accelerate"
                             " rotational per second")
    parser.add_argument('--tiltingAccelerationPerSecond',
                        type=int, default=400,
                        help="Defines how fast the gimbal may accelerate"
                             " in tilting direction per second")
    parser.add_argument('--variance',
                        type=int, default=80,
                        help="Defines the variance up to which no movement"
                             " (pan, tilt, zoom) occurs.")
    parser.add_argument('--liveViewWith',
                        type=int, default=640,
                        help="Width of live view of used camera")
    parser.add_argument('--liveViewHeight',
                        type=int, default=480,
                        help="Height of live view of used camera")
    parser.add_argument('--cameraMinFocalLength',
                        type=float, default=6.0,
                        help="Minimum focal length in millimeter"
                             "of the used camera. The actual focal length"
                             "and not the 35mm equivalent is expected.")
    parser.add_argument('--cameraMaxFocalLength',
                        type=float, default=42.8,
                        help="Maximum focal length in millimeter"
                             "of the used camera. The actual focal length"
                             "and not the 35mm equivalent is expected.")
    parser.add_argument(
        '--camera-zoom-steps',
        type=Path,
        default=None,
        help="Path to file that contains the configuration of the camera's"
             " zoom-steps (see"
             " robot_cameraman/tools/analyze_zoom_of_camera.py)."
             " If this argument is given,"
             " the PredictiveCameraZoomRatioLimitController is used to limit"
             " the zoom of the camera.")
    parser.add_argument(
        '--camera-zoom-ratio-index-ranges',
        type=Path,
        default=None,
        help="Path to file that contains the configuration of the camera's"
             " zoom-ratio-index-ranges (see"
             " analyze_zoom_indices_of_panasonic_camera.py and"
             " analyze_zoom_indices_of_panasonic_camera_interactively.py"
             " in directory robot_cameraman/tools)."
             " If this argument is given,"
             " the CameraZoomIndexLimitController is used to limit the"
             " zoom of the camera.")
    parser.add_argument(
        '--ssl-key',
        type=Path,
        default=resources / 'server.key',
        help="Path to server SSL-key file.")
    parser.add_argument(
        '--ssl-certificate',
        type=Path,
        default=resources / 'server.pem',
        help="Path to server SSL-certificate file.")
    # noinspection PyTypeChecker
    return parser.parse_args()


def quit(sig=None, frame=None):
    global cameraman_thread, to_exit
    print("Exiting...")
    to_exit.set()
    # TODO terminate server
    if threading.current_thread() != cameraman_thread:
        print('wait for cameraman thread')
        cameraman_thread.join()
    if threading.current_thread() != camera_manager:
        print('wait for camera manager thread')
        camera_manager.cancel()
        camera_manager.join()
    exit(0)


def run_cameraman():
    global server_image, to_exit, live_view_image_size
    cameraman.run(server_image, to_exit, live_view_image_size)
    quit()


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

    # some devices on the network may cause upnpclient.discover to log quite
    # verbose error messages. The log level is changed to avoid this
    logging.getLogger('ssdp').setLevel(logging.CRITICAL)
    # The web UI does frequent requests regarding the status bar
    # that spam the logs. Usually, those INFO logs are not important,
    # since the relevant interaction is covered by logs of other modules.
    # Hence, the log level of werkzeug is changed.
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


args = parse_arguments()
configure_logging()
configuration = read_configuration_file(args.config)
event_emitter = EventEmitter()
labels = read_label_file(args.labels)
font = PIL.ImageFont.truetype(str(args.font), args.fontSize)
live_view_image_size = ImageSize(args.liveViewWith, args.liveViewHeight)
destination = Destination(live_view_image_size, variance=args.variance)
camera_manager = PanasonicCameraManager(
    identify_as=args.identifyToPanasonicCameraAs)
max_speed_and_acceleration_updater = MaxSpeedAndAccelerationUpdater()
configurable_tracking_strategy = \
    ConfigurableTrackingStrategy(
        destination, live_view_image_size, max_allowed_speed=24)
tracking_strategy = StopIfLostTrackingStrategy(
    destination,
    max_speed_and_acceleration_updater.add(
        configurable_tracking_strategy),
    slow_down_time=1)
if args.gimbal == 'SimpleBGC':
    gimbal = create_simple_bgc_gimbal()
else:
    gimbal = DummyGimbal()
if args.gimbalTiltInverted:
    gimbal = TiltInvertedGimbal(gimbal)
rotate_speed_manager = max_speed_and_acceleration_updater.add(
    SpeedManager(args.rotationalAccelerationPerSecond))
tilt_speed_manager = max_speed_and_acceleration_updater.add(
    SpeedManager(args.tiltingAccelerationPerSecond))
configurable_align_tracking_strategy = \
    ConfigurableAlignTrackingStrategy(
        destination, live_view_image_size, max_allowed_speed=16)


def create_camera_zoom_limit_controller():
    global event_emitter
    if args.camera_zoom_ratio_index_ranges is not None:
        controller = CameraZoomIndexLimitController()
    elif args.camera_zoom_steps is not None:
        controller = PredictiveCameraZoomRatioLimitController(
            zoom_steps=parse_zoom_steps(args.camera_zoom_steps))
    else:
        controller = CameraZoomRatioLimitController()
    if hasattr(controller, 'update_zoom_ratio'):
        event_emitter.add_listener(
            Event.ZOOM_RATIO,
            controller.update_zoom_ratio)
    if hasattr(controller, 'update_zoom_index'):
        event_emitter.add_listener(
            Event.ZOOM_INDEX,
            controller.update_zoom_index)
    return controller


camera_zoom_limit_controller = create_camera_zoom_limit_controller()

if args.search_strategy == 'rotate':
    search_target_strategy = max_speed_and_acceleration_updater.add(
        RotateSearchTargetStrategy(args.rotatingSearchSpeed))
elif args.search_strategy == 'static':
    search_target_strategy = StaticSearchTargetStrategy(
        pan_speed=args.rotatingSearchSpeed,
        tilt_speed=args.rotatingSearchSpeed,
        camera_zoom_limit_controller=create_camera_zoom_limit_controller(),
        camera_angle_limit_controller=create_angle_limit_controller(
            event_emitter))
    event_emitter.add_listener(
        Event.ANGLES, search_target_strategy.update_current_angles)
    event_emitter.add_listener(
        Event.ZOOM_INDEX, search_target_strategy.update_current_zoom_index)
    event_emitter.add_listener(
        Event.ZOOM_RATIO, search_target_strategy.update_current_zoom_ratio)
else:
    print(f"Unknown search strategy {args.search_strategy}")
    exit(1)
camera_angle_limit_controller = create_angle_limit_controller(event_emitter)
# noinspection PyUnboundLocalVariable
cameraman_mode_manager = CameramanModeManager(
    camera_controller=SmoothCameraController(
        gimbal,
        camera_manager,
        rotate_speed_manager=rotate_speed_manager,
        tilt_speed_manager=tilt_speed_manager),
    camera_zoom_limit_controller=camera_zoom_limit_controller,
    camera_angle_limit_controller=camera_angle_limit_controller,
    align_tracking_strategy=max_speed_and_acceleration_updater.add(
        configurable_align_tracking_strategy),
    tracking_strategy=tracking_strategy,
    search_target_strategy=search_target_strategy,
    gimbal=gimbal,
    event_emitter=event_emitter)

# noinspection PyListCreation
user_interfaces = []

user_interfaces.append(
    ConfigurableTrackingStrategyUi(
        tracking_strategy=configurable_tracking_strategy,
        align_strategy=configurable_align_tracking_strategy))

# noinspection PyProtectedMember
status_bar = StatusBar(pan_speed_manager=rotate_speed_manager,
                       tilt_speed_manager=tilt_speed_manager,
                       camera_speeds=cameraman_mode_manager._camera_speeds)
event_emitter.add_listener(Event.ANGLES, status_bar.update_current_angles)
user_interfaces.append(status_bar)

if args.detectionEngine == 'Dummy':
    detection_engine = DummyDetectionEngine()
elif args.detectionEngine == 'Color':
    detection_engine = ColorDetectionEngine(
        target_label_id=args.targetLabelId,
        min_hsv=configuration['tracking']['color']['min_hsv'],
        max_hsv=configuration['tracking']['color']['max_hsv'])
    user_interfaces.append(
        ColorDetectionEngineUI(engine=detection_engine,
                               configuration_file=args.config))
elif args.detectionEngine == 'EdgeTPU':
    detection_engine = EdgeTpuDetectionEngine(
        model=args.model,
        confidence=args.confidence,
        max_objects=args.maxObjects)
else:
    print(f"Unknown detection engine {args.detectionEngine}")
    exit(1)

if args.liveView == 'Webcam':
    live_view = WebcamLiveView()
elif args.liveView == 'Dummy':
    live_view = DummyLiveView(live_view_image_size)
elif args.liveView == 'Panasonic':
    live_view = PanasonicLiveView(args.ip, args.port)
    camera_observable = PanasonicCameraObservable(
        min_focal_length=args.cameraMinFocalLength,
        event_emitter=event_emitter)
    live_view.add_ex_header_listener(camera_observable.on_ex_header)
    # TODO add CLI argument to enable ExHeaderToCsvWriter
    # noinspection PyUnreachableCode
    if False:
        from robot_cameraman.camera_observable import ExHeaderToCsvWriter

        live_view.add_ex_header_listener(ExHeaderToCsvWriter().on_ex_header)
    event_emitter.add_listener(
        Event.ZOOM_RATIO,
        max_speed_and_acceleration_updater.on_zoom_ratio)
    event_emitter.add_listener(
        Event.ZOOM_INDEX,
        status_bar.update_zoom_index)
    event_emitter.add_listener(
        Event.ZOOM_RATIO,
        status_bar.update_zoom_ratio)
    if hasattr(camera_zoom_limit_controller, 'update_zoom_ratio'):
        event_emitter.add_listener(
            Event.ZOOM_RATIO,
            camera_zoom_limit_controller.update_zoom_ratio)
    if hasattr(camera_zoom_limit_controller, 'update_zoom_index'):
        event_emitter.add_listener(
            Event.ZOOM_INDEX,
            camera_zoom_limit_controller.update_zoom_index)
elif args.liveView == 'File':
    video_or_image_file = open_file_dialog()
    if not video_or_image_file:
        print(f"No file selected")
        exit(1)
    live_view = FileLiveView(file=video_or_image_file)
else:
    print(f"Unknown live view {args.liveView}")
    exit(1)

manual_camera_speeds = max_speed_and_acceleration_updater.add(
    CameraSpeeds(pan_speed=8, tilt_speed=4, zoom_speed=ZoomSpeed.ZOOM_IN_SLOW))
# noinspection PyUnboundLocalVariable
cameraman = Cameraman(
    live_view=live_view,
    annotator=ImageAnnotator(args.targetLabelId, labels, font),
    detection_engine=detection_engine,
    destination=destination,
    mode_manager=cameraman_mode_manager,
    object_tracker=ObjectTracker(max_disappeared=25),
    target_label_id=args.targetLabelId,
    output=create_video_writer(args.output, live_view_image_size),
    user_interfaces=user_interfaces,
    # TODO get max speeds from separate CLI arguments
    manual_camera_speeds=manual_camera_speeds)

to_exit = threading.Event()
server_image = ImageContainer(
    image=PIL.Image.new('RGB', live_view_image_size, color=(73, 109, 137)))

signal.signal(signal.SIGINT, quit)
signal.signal(signal.SIGTERM, quit)

camera_manager.start()
cameraman_thread = threading.Thread(target=run_cameraman, daemon=True)
cameraman_thread.start()
print('Open https://localhost:9000/index.html in your browser')
camera_zoom_ratio_index_ranges = (
    None if args.camera_zoom_ratio_index_ranges is None
    else parse_zoom_ratio_index_ranges(args.camera_zoom_ratio_index_ranges))
run_server(_to_exit=to_exit,
           _cameraman_mode_manager=cameraman_mode_manager,
           _server_image=server_image,
           _manual_camera_speeds=manual_camera_speeds,
           _updatable_configuration=UpdatableConfiguration(
               detection_engine=detection_engine,
               cameraman_mode_manager=cameraman_mode_manager,
               camera_zoom_limit_controller=camera_zoom_limit_controller,
               camera_angle_limit_controller=camera_angle_limit_controller,
               configuration_file=args.config,
               camera_zoom_ratio_index_ranges=camera_zoom_ratio_index_ranges,
               search_target_strategy=search_target_strategy),
           _status_bar=status_bar,
           ssl_certificate=args.ssl_certificate,
           ssl_key=args.ssl_key)
