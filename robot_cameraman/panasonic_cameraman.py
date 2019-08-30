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
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
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
from robot_cameraman.tracking import Destination, CameraController

# Variable to store command line arguments
ARGS = None
to_exit: threading.Event = threading.Event()
server_image: PIL.Image
server: ThreadingHTTPServer
live_view: LiveView


class RobotCameramanHttpHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Content-type',
                             'multipart/x-mixed-replace; boundary=jpgboundary')
            self.end_headers()
            global to_exit, server_image
            while not to_exit.wait(0.05):
                # rc, img = capture.read()
                # if not rc:
                #     continue
                # image_rgb = cv2.cvtColor(server_image, cv2.COLOR_BGR2RGB)
                image_rgb = server_image
                jpg = PIL.Image.fromarray(image_rgb)
                jpg_bytes = jpg.tobytes()
                self.wfile.write(str.encode("\r\n--jpgboundary\r\n"))
                self.send_header('Content-type', 'image/jpeg')
                self.send_header('Content-length', len(jpg_bytes))
                self.end_headers()
                jpg.save(self.wfile, 'JPEG')
            return
        if self.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write("""
                    <html>
                        <head></head>
                        <body><img src="cam.mjpg"/></body>
                    </html>
                """.encode())
            return


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


# Main flow
def main() -> None:
    # Store labels for matching with inference results
    labels = read_label_file(ARGS.labels) if ARGS.labels else None

    # Specify font for labels
    # font = PIL.ImageFont.truetype("/usr/share/fonts/truetype/piboto/Piboto-Regular.ttf", 20)
    font = PIL.ImageFont.truetype(
        "/usr/share/fonts/truetype/roboto/hinted/Roboto-Regular.ttf", 30)
    # font = None
    engine = edgetpu.detection.engine.DetectionEngine(str(ARGS.model))

    width = 640
    height = 480
    out = cv2.VideoWriter('output.avi',
                          cv2.VideoWriter_fourcc(*'MJPG'),
                          30,
                          (width, height))

    # Use imutils to count Frames Per Second (FPS)
    fps = FPS().start()

    global live_view, server_image, to_exit
    live_view = LiveView(ARGS.ip, ARGS.port)
    annotator = ImageAnnotator(ARGS.targetLabelId, labels, font)
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
                annotator.annotate(image, inference_results)
                target = annotator.target
                camera_controller.update(None if target is None else target.box)
            except OSError as e:
                print(e)
                pass

            image_array = numpy.asarray(image)
            # server_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            server_image = image_array
            cv2_image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            # out.write(cv2_image)
            if 'DISPLAY' in os.environ:
                cv2.imshow('NCS Improved live inference', cv2_image)

            # Display the frame for 5ms, and close the window so that the next
            # frame can be displayed. Close the window if 'q' or 'Q' is pressed.
            if cv2.waitKey(5) & 0xFF == ord('q'):
                fps.stop()
                camera_controller.stop()
                break

            fps.update()

        # Allows graceful exit using ctrl-c (handy for headless mode).
        except KeyboardInterrupt:
            fps.stop()
            break

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
    threading.Thread(target=main, daemon=True).start()
    server = ThreadingHTTPServer(('', 9000), RobotCameramanHttpHandler)
    print('Open http://localhost:9000/index.html in your browser')
    server.serve_forever()
