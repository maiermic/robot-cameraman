# inspired by article "Ball Tracking with OpenCV" by Adrian Rosebrock
# https://pyimagesearch.com/2015/09/14/ball-tracking-with-opencv/

import logging
from logging import Logger
from typing import Iterable

import cv2
import imutils
import numpy

from robot_cameraman.box import Box, Point
from robot_cameraman.image_detection import DetectionEngine, DetectionCandidate
from robot_cameraman.ui import UserInterface

logger: Logger = logging.getLogger(__name__)


class ColorDetectionEngine(DetectionEngine):
    def __init__(self, target_label_id: int, min_hsv=(0, 0, 0),
                 max_hsv=(0, 0, 0)) -> None:
        self.target_label_id = target_label_id
        self.min_hsv = numpy.asarray(min_hsv)
        self.max_hsv = numpy.asarray(max_hsv)
        self.mask = None
        self.is_single_object_detection = True
        self.minimum_contour_radius = 20

    def detect(self, image) -> Iterable[DetectionCandidate]:
        image_array = numpy.asarray(image)
        # reduce high frequency noise
        # to focus on the structural objects inside the frame
        blurred = cv2.GaussianBlur(image_array, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_RGB2HSV)

        self.mask = cv2.inRange(hsv, self.min_hsv, self.max_hsv)
        # remove any small blobs left in the mask
        self.mask = cv2.erode(self.mask, None, iterations=2)
        self.mask = cv2.dilate(self.mask, None, iterations=2)

        contours = cv2.findContours(self.mask.copy(), cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
        contours = imutils.grab_contours(contours)

        return self._contours_to_detection_candidates(contours)

    def _contours_to_detection_candidates(self, contours):
        if self.is_single_object_detection and len(contours) > 0:
            contours = [max(contours, key=cv2.contourArea)]
        for contour in contours:
            (x, y), radius = cv2.minEnclosingCircle(contour)
            if radius > self.minimum_contour_radius:
                size = 2 * radius
                bounding_box = \
                    Box.from_center_and_size(
                        center=Point(x, y),
                        width=size,
                        height=size)
                yield DetectionCandidate(
                    label_id=self.target_label_id,
                    score=1.0,
                    bounding_box=bounding_box)


class ColorDetectionEngineUI(UserInterface):
    def __init__(
            self,
            engine: ColorDetectionEngine,
            window_title: str = 'Mask') -> None:
        self.engine = engine
        self._window_title = window_title

    def open(self):
        cv2.namedWindow('Mask', cv2.WINDOW_NORMAL)
        self._setup_hsv_trackbars()
        cv2.createButton(
            'Single Object Detection',
            self._toggle_single_object_detection,
            None,
            cv2.QT_CHECKBOX,
            1 if self.engine.is_single_object_detection else 0)

    def _toggle_single_object_detection(self, value, _user_data):
        self.engine.is_single_object_detection = value == 1
        logger.error('single object detection '
                     'enabled' if self.engine.is_single_object_detection
                     else 'disabled')

    def _setup_hsv_trackbars(self):
        def min_change(index):
            def on_min_change(value):
                self.engine.min_hsv[index] = value

            return on_min_change

        min_h, min_s, min_v, = self.engine.min_hsv
        self._create_trackbar('MIN_H', min_h, min_change(0))
        self._create_trackbar('MIN_S', min_s, min_change(1))
        self._create_trackbar('MIN_V', min_v, min_change(2))

        def max_change(index):
            def on_max_change(value):
                self.engine.max_hsv[index] = value

            return on_max_change

        max_h, max_s, max_v, = self.engine.max_hsv
        self._create_trackbar('MAX_H', max_h, max_change(0))
        self._create_trackbar('MAX_S', max_s, max_change(1))
        self._create_trackbar('MAX_V', max_v, max_change(2))

    def _create_trackbar(self, name, value, on_change):
        cv2.createTrackbar(name, self._window_title, value, 255, on_change)

    def update(self):
        if self.engine.mask is not None:
            cv2.imshow('Mask', self.engine.mask)
        else:
            logger.error('Mask is None')
