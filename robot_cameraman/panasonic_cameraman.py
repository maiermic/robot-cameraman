#!/usr/bin/python3

#
# ****************************************************************************
# Detect and annotate objects in a video file using the Google Coral USB Stick.
#
# ****************************************************************************
#

import argparse
import io
import os
import signal
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import cv2
import edgetpu.detection.engine
import numpy
from imutils.video import FPS

from panasonic_camera.live_view import LiveView
from robot_cameraman.annotation import ImageAnnotator, draw_destination
from robot_cameraman.resource import read_label_file
from robot_cameraman.server import RobotCameramanHttpHandler, ImageContainer
from robot_cameraman.tracking import Destination, CameraController

# Variable to store command line arguments
ARGS = None
to_exit: threading.Event = threading.Event()
server_image: ImageContainer = ImageContainer(image=None)
server: ThreadingHTTPServer


def quit(sig=None, frame=None):
    print("Exiting...")
    global to_exit
    global server
    to_exit.set()
    # Regular server.shutdown() waits forever if server.serve_forever() is not
    # running anymore. Hence, this work around that only sets the flag to
    # shutdown, but does not wait.
    server._BaseServer__shutdown_request = True
    exit(0)


class PanasonicCameraman:

    def __init__(self, annotator: ImageAnnotator) -> None:
        self.annotator = annotator

    def run(self) -> None:
        engine = edgetpu.detection.engine.DetectionEngine(str(ARGS.model))

        width = 640
        height = 480
        out = cv2.VideoWriter('output.avi',
                              cv2.VideoWriter_fourcc(*'MJPG'),
                              30,
                              (width, height))

        # Use imutils to count Frames Per Second (FPS)
        fps = FPS().start()

        global server_image, to_exit
        live_view = LiveView(ARGS.ip, ARGS.port)
        destination = None
        camera_controller = None
        while not to_exit.is_set():
            try:
                image = PIL.Image.open(io.BytesIO(live_view.image()))
                if destination is None:
                    destination = Destination(image.size, variance=20)
                    camera_controller = CameraController(destination)
                # Perform inference and note time taken
                start_ms = time.time()
                try:
                    inference_results = engine.DetectWithImage(image,
                                                               threshold=ARGS.confidence,
                                                               keep_aspect_ratio=True,
                                                               relative_coord=False,
                                                               top_k=ARGS.maxobjects)
                    draw_destination(image, destination)
                    self.annotator.annotate(image, inference_results)
                    target = self.annotator.target
                    camera_controller.update(
                        None if target is None else target.box)
                except OSError as e:
                    print(e)
                    pass

                server_image.image = image
                cv2_image = cv2.cvtColor(numpy.asarray(image),
                                         cv2.COLOR_RGB2BGR)
                # out.write(cv2_image)
                if 'DISPLAY' in os.environ:
                    cv2.imshow('NCS Improved live inference', cv2_image)

                # Display the frame for 5ms, and close the window so that the next
                # frame can be displayed. Close the window if 'q' or 'Q' is pressed.
                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break

                fps.update()

            # Allows graceful exit using ctrl-c (handy for headless mode).
            except KeyboardInterrupt:
                break

        if camera_controller:
            print('Stop camera')
            camera_controller.stop()
        fps.stop()
        print("Elapsed time: " + str(fps.elapsed()))
        print("Approx FPS: :" + str(fps.fps()))

        cv2.destroyAllWindows()
        quit()


if __name__ == '__main__':
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

    parser.add_argument('--maxobjects', type=int,
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

    ARGS = parser.parse_args()

    signal.signal(signal.SIGINT, quit)
    signal.signal(signal.SIGTERM, quit)

    labels = read_label_file(ARGS.labels) if ARGS.labels else None
    font = PIL.ImageFont.truetype(
        "/usr/share/fonts/truetype/roboto/hinted/Roboto-Regular.ttf", 30)
    cameraman = PanasonicCameraman(
        annotator=ImageAnnotator(ARGS.targetLabelId, labels, font))
    threading.Thread(target=cameraman.run, daemon=True).start()

    RobotCameramanHttpHandler.to_exit = to_exit
    RobotCameramanHttpHandler.server_image = server_image
    server = ThreadingHTTPServer(('', 9000), RobotCameramanHttpHandler)
    print('Open http://localhost:9000/index.html in your browser')
    server.serve_forever()
