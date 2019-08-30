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
from typing import Dict, List, Tuple, Optional, NamedTuple

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import cv2
import edgetpu.detection.engine
import numpy
from PIL.ImageDraw import ImageDraw
from PIL.ImageFont import FreeTypeFont
from edgetpu.detection.engine import DetectionCandidate
from imutils.video import FPS

from panasonic_camera.live_view import LiveView
from robot_cameraman.box import center, Box
from robot_cameraman.resource import read_label_file
from robot_cameraman.tracking import Destination, CameraController

# Variable to store command line arguments
ARGS = None
to_exit: bool = False
server_image: PIL.Image
server: ThreadingHTTPServer
live_view: LiveView


class Target(NamedTuple):
    box: Box
    detection_candidate: DetectionCandidate


class ImageAnnotator:
    target: Optional[Target] = None

    def __init__(
            self,
            target_label_id: int,
            labels: Dict[int, str],
            font: FreeTypeFont) -> None:
        self.target_label_id = target_label_id
        self.labels = labels
        self.font = font

    def annotate(
            self,
            image: PIL.Image.Image,
            inference_results: List[DetectionCandidate]) -> Optional[Target]:
        draw = PIL.ImageDraw.Draw(image)
        # Iterate through result list. Note that results are already sorted by
        # confidence score (highest to lowest) and records with a lower score
        # than the threshold are already removed.
        target_box_found = False
        for idx, obj in enumerate(inference_results):
            box = obj.bounding_box.flatten().tolist()
            if obj.label_id != self.target_label_id:
                color = (255, 255, 255)
            else:
                color = (0, 255, 0)
                if not target_box_found:
                    target_box_found = True
                    self.target = Target(box, obj)
            self.draw_annotated_box(draw, box, obj, color)
        if self.target is None or target_box_found:
            return
        self.draw_annotated_box(draw, self.target.box,
                                self.target.detection_candidate,
                                (255, 0, 0))

    def draw_annotated_box(
            self,
            draw: ImageDraw,
            box: List[float],
            obj: DetectionCandidate,
            color: Tuple[int, int, int]) -> None:
        draw.rectangle(box, outline=color)
        draw_point(draw, center(box), color)
        # Annotate image with label and confidence score
        display_str = self.labels[obj.label_id] + ": " + str(
            round(obj.score * 100, 2)) + "%"
        draw.text((box[0], box[1]), display_str, font=self.font)


def draw_destination(
        image: PIL.Image.Image,
        destination: Destination,
        color: Tuple[int, int, int] = (255, 0, 255)) -> None:
    draw = PIL.ImageDraw.Draw(image)
    draw_point(draw, destination.center, color)
    draw.rectangle(destination.box, outline=color)


def draw_point(
        draw: ImageDraw,
        point: Tuple[float, float],
        color: Tuple[int, int, int],
        radius: int = 3) -> None:
    x, y = point
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


class RobotCameramanHttpHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Content-type',
                             'multipart/x-mixed-replace; boundary=jpgboundary')
            self.end_headers()
            global to_exit, server_image
            while not to_exit:
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
                time.sleep(0.05)
                # break
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
    to_exit = True
    server.shutdown()
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
    while not to_exit:
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
