import argparse
import logging
import signal
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import PIL.ImageFont
import cv2

from panasonic_camera.camera_manager import PanasonicCameraManager
from panasonic_camera.live_view import LiveView
from robot_cameraman.annotation import ImageAnnotator
from robot_cameraman.camera_controller import SmoothCameraController
from robot_cameraman.cameraman_mode_manager import CameramanModeManager
from robot_cameraman.image_detection import DetectionEngine
from robot_cameraman.object_tracking import ObjectTracker
from robot_cameraman.panasonic_cameraman import PanasonicCameraman
from robot_cameraman.resource import read_label_file
from robot_cameraman.server import RobotCameramanHttpHandler, ImageContainer
from robot_cameraman.tracking import Destination, SimpleTrackingStrategy, \
    StopIfLostTrackingStrategy, SimpleAlignTrackingStrategy

to_exit: threading.Event
server: ThreadingHTTPServer
server_image: ImageContainer


def create_video_writer(output_file: Path):
    width = 640
    height = 480
    return cv2.VideoWriter(
        str(output_file),
        cv2.VideoWriter_fourcc(*'MJPG'),
        30,
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
    return parser.parse_args()


def quit(sig=None, frame=None):
    global cameraman_thread, server, to_exit
    print("Exiting...")
    to_exit.set()
    # Regular server.shutdown() waits forever if server.serve_forever() is
    # not running anymore. Hence, this work around that only sets the flag
    # to shutdown, but does not wait.
    server._BaseServer__shutdown_request = True
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


args = parse_arguments()
logging.basicConfig(level=logging.DEBUG if args.debug else logging.ERROR)
labels = read_label_file(args.labels)
font = PIL.ImageFont.truetype(str(args.font), args.fontSize)
destination = Destination((640, 480), variance=80)
camera_manager = PanasonicCameraManager()
cameraman_mode_manager = CameramanModeManager(
    camera_controller=SmoothCameraController(camera_manager),
    align_tracking_strategy=SimpleAlignTrackingStrategy(destination,
                                                        max_allowed_speed=200),
    tracking_strategy=StopIfLostTrackingStrategy(destination,
                                                 SimpleTrackingStrategy(
                                                     destination,
                                                     max_allowed_speed=500),
                                                 slow_down_time=1))
cameraman = PanasonicCameraman(
    live_view=LiveView(args.ip, args.port),
    annotator=ImageAnnotator(args.targetLabelId, labels, font),
    detection_engine=DetectionEngine(
        model=args.model,
        confidence=args.confidence,
        max_objects=args.maxObjects),
    destination=destination,
    mode_manager=cameraman_mode_manager,
    object_tracker=ObjectTracker(),
    target_label_id=args.targetLabelId,
    output=create_video_writer(args.output))

to_exit = threading.Event()
server_image = ImageContainer(image=None)
RobotCameramanHttpHandler.to_exit = to_exit
RobotCameramanHttpHandler.server_image = server_image
RobotCameramanHttpHandler.cameraman_mode_manager = cameraman_mode_manager
server = ThreadingHTTPServer(('', 9000), RobotCameramanHttpHandler)

signal.signal(signal.SIGINT, quit)
signal.signal(signal.SIGTERM, quit)

camera_manager.start()
cameraman_thread = threading.Thread(target=run_cameraman, daemon=True)
cameraman_thread.start()
print('Open http://localhost:9000/index.html in your browser')
server.serve_forever()
