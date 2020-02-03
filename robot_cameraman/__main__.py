import argparse
import logging
import signal
import threading
# noinspection Mypy
from pathlib import Path

import PIL.Image
import PIL.ImageFont
import cv2

from panasonic_camera.camera_manager import PanasonicCameraManager
from panasonic_camera.live_view import LiveView
from robot_cameraman.annotation import ImageAnnotator
from robot_cameraman.camera_controller import SmoothCameraController, \
    SpeedManager
from robot_cameraman.cameraman_mode_manager import CameramanModeManager
from robot_cameraman.image_detection import DetectionEngine
from robot_cameraman.object_tracking import ObjectTracker
from robot_cameraman.panasonic_cameraman import PanasonicCameraman
from robot_cameraman.resource import read_label_file
from robot_cameraman.server import run_server, ImageContainer
from robot_cameraman.tracking import Destination, SimpleTrackingStrategy, \
    StopIfLostTrackingStrategy, SimpleAlignTrackingStrategy, \
    RotateSearchTargetStrategy

to_exit: threading.Event
server_image: ImageContainer


def create_video_writer(output_file: Path):
    width = 640
    height = 480
    return cv2.VideoWriter(
        str(output_file),
        cv2.VideoWriter_fourcc(*'MJPG'),
        15,
        (width, height))


def parse_arguments():
    resources: Path = Path(__file__).parent / 'resources'
    mobilenet = 'mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite'
    parser = argparse.ArgumentParser(
        description="Detect objects in a video file using Google Coral USB.")
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
    parser.add_argument('--ip', type=str,
                        default='0.0.0.0',
                        help="UDP Socket IP address.")
    parser.add_argument('--port', type=int,
                        default=49199,
                        help="UDP Socket port.")
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
    global server_image, to_exit
    cameraman.run(server_image, to_exit)
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


args = parse_arguments()
configure_logging()
labels = read_label_file(args.labels)
font = PIL.ImageFont.truetype(str(args.font), args.fontSize)
destination = Destination((640, 480), variance=args.variance)
camera_manager = PanasonicCameraManager()
tracking_strategy = StopIfLostTrackingStrategy(
    destination,
    SimpleTrackingStrategy(destination, max_allowed_speed=500),
    slow_down_time=1)
cameraman_mode_manager = CameramanModeManager(
    camera_controller=SmoothCameraController(
        camera_manager,
        rotate_speed_manager=SpeedManager(args.rotationalAccelerationPerSecond),
        tilt_speed_manager=SpeedManager(args.tiltingAccelerationPerSecond)),
    align_tracking_strategy=SimpleAlignTrackingStrategy(destination,
                                                        max_allowed_speed=200),
    tracking_strategy=tracking_strategy,
    search_target_strategy=RotateSearchTargetStrategy(args.rotatingSearchSpeed))
cameraman = PanasonicCameraman(
    live_view=LiveView(args.ip, args.port),
    annotator=ImageAnnotator(args.targetLabelId, labels, font),
    detection_engine=DetectionEngine(
        model=args.model,
        confidence=args.confidence,
        max_objects=args.maxObjects),
    destination=destination,
    mode_manager=cameraman_mode_manager,
    object_tracker=ObjectTracker(max_disappeared=25),
    target_label_id=args.targetLabelId,
    output=create_video_writer(args.output))

to_exit = threading.Event()
server_image = ImageContainer(
    image=PIL.Image.new('RGB', (640, 480), color=(73, 109, 137)))

signal.signal(signal.SIGINT, quit)
signal.signal(signal.SIGTERM, quit)

camera_manager.start()
cameraman_thread = threading.Thread(target=run_cameraman, daemon=True)
cameraman_thread.start()
print('Open https://localhost:9000/index.html in your browser')
run_server(_to_exit=to_exit,
           _cameraman_mode_manager=cameraman_mode_manager,
           _server_image=server_image,
           ssl_certificate=args.ssl_certificate,
           ssl_key=args.ssl_key)
