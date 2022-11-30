#!/usr/bin/python3

#
# ****************************************************************************
# Detect and annotate objects in a video file using the Google Coral USB Stick.
#
# ****************************************************************************
#

import argparse
import os
from typing import Dict, List

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import cv2
import numpy
import time
from imutils.video import FPS

from panasonic_camera.camera_manager import PanasonicCameraManager
from robot_cameraman.image_detection import EdgeTpuDetectionEngine, \
    DetectionCandidate
from robot_cameraman.live_view import PanasonicLiveView
from robot_cameraman.resource import read_label_file

# Variable to store command line arguments
ARGS = None


def annotate(
        image: PIL.Image.Image,
        inferenceResults: List[DetectionCandidate],
        elapsedMs: float,
        labels: Dict[int, str],
        font: PIL.ImageFont.FreeTypeFont) -> None:
    # Iterate through result list. Note that results are already sorted by
    # confidence score (highest to lowest) and records with a lower score
    # than the threshold are already removed.
    result_size = len(inferenceResults)
    for idx, obj in enumerate(inferenceResults):

        # Prepare image for drawing
        draw = PIL.ImageDraw.Draw(image)

        # Prepare boundary box
        box = obj.bounding_box

        # Draw rectangle to desired thickness
        for x in range(0, 4):
            draw.rectangle(box.coordinates(), outline=(255, 255, 0))

        # Annotate image with label and confidence score
        display_str = labels[obj.label_id] + ": " + str(
            round(obj.score * 100, 2)) + "%"
        draw.text((box.x, box.y), display_str, font=font)

        # Log the current result to terminal
        print("Object (" + str(idx + 1) + " of " + str(result_size) + "): "
              + labels[obj.label_id] + " (" + str(obj.label_id) + ")"
              + ", Confidence:" + str(obj.score)
              + ", Elapsed:" + str(elapsedMs * 1000.0) + "ms"
              + ", Box:" + str(box))


# Main flow
def main() -> None:
    # Store labels for matching with inference results
    labels = read_label_file(ARGS.labels) if ARGS.labels else None

    # Specify font for labels
    # font = PIL.ImageFont.truetype("/usr/share/fonts/truetype/piboto/Piboto-Regular.ttf", 20)
    font = PIL.ImageFont.truetype(
        "/usr/share/fonts/truetype/roboto/hinted/Roboto-Regular.ttf", 30)
    # font = None
    engine = EdgeTpuDetectionEngine(
        model=ARGS.model,
        confidence=ARGS.confidence,
        max_objects=ARGS.maxobjects)

    width = 640
    height = 480
    out = cv2.VideoWriter('output.avi',
                          cv2.VideoWriter_fourcc(*'MJPG'),
                          30,
                          (width, height))

    # Use imutils to count Frames Per Second (FPS)
    fps = FPS().start()

    camera_manager = PanasonicCameraManager()
    camera_manager.start()
    live_view = PanasonicLiveView(ARGS.ip, ARGS.port)
    while True:
        try:
            try:
                image = live_view.image()
            except OSError:
                print('could not identify image file')
                continue
            if image is None:
                continue
            # Perform inference and note time taken
            startMs = time.time()
            try:
                inferenceResults = list(engine.detect(image))
                elapsedMs = time.time() - startMs

                annotate(image, inferenceResults, elapsedMs, labels, font)
            except OSError as e:
                print(e)
                pass

            cv2_image = cv2.cvtColor(numpy.asarray(image), cv2.COLOR_RGB2BGR)
            out.write(cv2_image)
            if 'DISPLAY' in os.environ:
                cv2.imshow('NCS Improved live inference', cv2_image)

            # Display the frame for 5ms, and close the window so that the next
            # frame can be displayed. Close the window if 'q' or 'Q' is pressed.
            if cv2.waitKey(5) & 0xFF == ord('q'):
                fps.stop()
                break

            fps.update()

        # Allows graceful exit using ctrl-c (handy for headless mode).
        except KeyboardInterrupt:
            fps.stop()
            break

    print("Elapsed time: " + str(fps.elapsed()))
    print("Approx FPS: :" + str(fps.fps()))

    cv2.destroyAllWindows()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Detect objects in a video file using Google Coral USB.")

    parser.add_argument('--model', type=str,
                        default='resources/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite',
                        help="Path to the neural network graph file.")

    parser.add_argument('--labels', type=str,
                        default='resources/coco_labels.txt',
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

    ARGS = parser.parse_args()

    main()
