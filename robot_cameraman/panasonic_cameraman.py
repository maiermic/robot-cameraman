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
import time

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import cv2
import edgetpu.detection.engine
import numpy
from imutils.video import FPS

from panasonic_camera.live_view import LiveView
from robot_cameraman.resource import read_label_file
from simplebgc.serial_example import rotate_gimbal

# Variable to store command line arguments
ARGS = None

# Last detected box of tracked object
target_box = None
target_detection_candidate = None


def center(box):
    x1, y1, x2, y2 = box
    return abs(x1 + x2) / 2, abs(y1 + y2) / 2


class ImageAnnotator:
    def __init__(self, labels, font):
        self.labels = labels
        self.font = font

    def annotate(self, image, inference_results):
        global target_box
        global target_detection_candidate
        draw = PIL.ImageDraw.Draw(image)
        # Iterate through result list. Note that results are already sorted by
        # confidence score (highest to lowest) and records with a lower score
        # than the threshold are already removed.
        target_box_found = False
        for idx, obj in enumerate(inference_results):
            box = obj.bounding_box.flatten().tolist()
            if obj.label_id != ARGS.targetLabelId:
                color = (255, 255, 255)
            else:
                color = (0, 255, 0)
                if not target_box_found:
                    target_box_found = True
                    target_box = box
                    target_detection_candidate = obj
            self.draw_annotated_box(draw, box, obj, color)
        if target_box is None or target_box_found:
            return
        self.draw_annotated_box(draw, target_box, target_detection_candidate,
                                (255, 0, 0))

    def draw_annotated_box(self, draw, box, obj, color):
        draw.rectangle(box, outline=color)
        draw_point(draw, center(box), color)
        # Annotate image with label and confidence score
        display_str = self.labels[obj.label_id] + ": " + str(
            round(obj.score * 100, 2)) + "%"
        draw.text((box[0], box[1]), display_str, font=self.font)


class Destination:

    def __init__(self, image_size, variance=50):
        width, height = image_size
        x, y = width / 2, height / 2
        self.center = (x, y)
        self.box = (x - variance, 0,
                    x + variance, height)
        self.variance = variance


def draw_destination(image, destination, color=(255, 0, 255)):
    draw = PIL.ImageDraw.Draw(image)
    draw_point(draw, destination.center, color)
    draw.rectangle(destination.box, outline=color)


def draw_point(draw, point, color, radius=3):
    x, y = point
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


max_speed = 0


class CameraController:

    def __init__(self, destination, max_allowed_speed=1000):
        self.destination = destination
        self.max_allowed_speed = max_allowed_speed
        self.search_speed = round(max_allowed_speed / 2)
        self.yaw_speed = 0

    def is_camera_moving(self):
        return self.yaw_speed != 0

    def stop(self):
        self.rotate(0)

    def rotate(self, yaw_speed):
        if self.yaw_speed != yaw_speed:
            self.yaw_speed = yaw_speed
            rotate_gimbal(self.yaw_speed)

    def update(self):
        if target_box is None:
            self.search_target()
        else:
            self.move_to_target()

    def move_to_target(self):
        global target_box
        global max_speed
        tx, ty = center(target_box)
        dx, dy = self.destination.center
        distance = tx - dx
        # print(distance)
        abs_distance = abs(distance)
        if abs_distance < self.destination.variance:
            if self.is_camera_moving():
                self.stop()
        else:
            # TODO check speed range of 2s is -32,768 to 32,767
            # image_width / speed_steps = 640 / 20 = 32
            # max_allowed_speed / speed_steps = 1000 / 20 = 100
            speed = round(abs_distance / 32 * 100)
            if speed > max_speed:
                print(speed)
                max_speed = speed
                if speed > self.max_allowed_speed:
                    print('surpassed maximum speed')
            speed = min(self.max_allowed_speed, speed)
            if distance < 0:
                speed = -speed
            self.rotate(speed)

    def rotate_right(self):
        self.rotate(100)

    def rotate_left(self):
        self.rotate(-100)

    def search_target(self):
        self.rotate(self.search_speed)


# Main flow
def main():
    # Store labels for matching with inference results
    labels = read_label_file(ARGS.labels) if ARGS.labels else None

    # Specify font for labels
    # font = PIL.ImageFont.truetype("/usr/share/fonts/truetype/piboto/Piboto-Regular.ttf", 20)
    font = PIL.ImageFont.truetype(
        "/usr/share/fonts/truetype/roboto/hinted/Roboto-Regular.ttf", 30)
    # font = None
    engine = edgetpu.detection.engine.DetectionEngine(ARGS.model)

    width = 640
    height = 480
    out = cv2.VideoWriter('output.avi',
                          cv2.VideoWriter_fourcc(*'MJPG'),
                          30,
                          (width, height))

    # Use imutils to count Frames Per Second (FPS)
    fps = FPS().start()

    live_view = LiveView(ARGS.ip, ARGS.port)
    annotator = ImageAnnotator(labels, font)
    destination = None
    camera_controller = None
    while True:
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
                camera_controller.update()
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

    parser.add_argument('--targetLabelId', type=int,
                        default=0,
                        help="ID of label to track.")

    ARGS = parser.parse_args()

    main()
