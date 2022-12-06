# inspired by article "Ball Tracking with OpenCV" by Adrian Rosebrock
# https://pyimagesearch.com/2015/09/14/ball-tracking-with-opencv/

import logging
from logging import Logger
from pathlib import Path
from typing import Iterable, Optional

import cv2
import imutils
import numpy

from robot_cameraman.box import Box
from robot_cameraman.configuration import read_configuration_file, \
    save_configuration_file
from robot_cameraman.image_detection import DetectionEngine, DetectionCandidate
from robot_cameraman.ui import UserInterface, create_attribute_checkbox

logger: Logger = logging.getLogger(__name__)


class ColorDetectionEngine(DetectionEngine):
    def __init__(
            self,
            target_label_id: int,
            is_single_object_detection: bool,
            min_hsv=(0, 0, 0),
            max_hsv=(0, 0, 0)) -> None:
        self.target_label_id = target_label_id
        self.min_hsv = numpy.asarray(min_hsv)
        self.max_hsv = numpy.asarray(max_hsv)
        self.mask = None
        self.mask_ui = None
        self.is_single_object_detection = is_single_object_detection
        self.minimum_contour_size = 20

    def detect(self, image) -> Iterable[DetectionCandidate]:
        image_array = numpy.asarray(image)
        # reduce high frequency noise
        # to focus on the structural objects inside the frame
        blurred = cv2.GaussianBlur(image_array, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_RGB2HSV)

        if self.min_hsv[0] <= self.max_hsv[0]:
            self.mask = cv2.inRange(hsv, self.min_hsv, self.max_hsv)
        else:
            max_h, max_s, max_v = self.max_hsv
            min_h, min_s, min_v = self.min_hsv
            mask_1 = cv2.inRange(
                hsv, self.min_hsv, numpy.asarray((255, max_s, max_v)))
            mask_2 = cv2.inRange(
                hsv, numpy.asarray((0, min_s, min_v)), self.max_hsv)
            self.mask = cv2.bitwise_or(mask_1, mask_2)
        # remove any small blobs left in the mask
        self.mask = cv2.erode(self.mask, None, iterations=2)
        self.mask = cv2.dilate(self.mask, None, iterations=2)

        if self.mask_ui is None:
            self.mask_ui = self.mask.copy()
        self.mask_ui = cv2.bitwise_and(image_array, image_array, mask=self.mask)

        contours = cv2.findContours(self.mask.copy(), cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
        contours = imutils.grab_contours(contours)

        return self._contours_to_detection_candidates(contours)

    def _contours_to_detection_candidates(self, contours):
        if self.is_single_object_detection and len(contours) > 0:
            contours = [max(contours, key=cv2.contourArea)]
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w + h > 4 * self.minimum_contour_size:
                bounding_box = \
                    Box.from_coordinates(x, y, x + w, y + h)
                yield DetectionCandidate(
                    label_id=self.target_label_id,
                    score=1.0,
                    bounding_box=bounding_box)


class ColorDetectionEngineUI(UserInterface):
    def __init__(
            self,
            engine: ColorDetectionEngine,
            window_title: str = 'Mask',
            configuration_file: Optional[Path] = None) -> None:
        self.engine = engine
        self._window_title = window_title
        self._configuration_file = configuration_file

    def open(self):
        cv2.namedWindow('Mask', cv2.WINDOW_NORMAL)
        self._create_trackbar(
            'Min Contour Size (width + height)',
            self.engine.minimum_contour_size,
            self._update_minimum_contour_radius)
        self._setup_hsv_trackbars()
        create_attribute_checkbox(
            'Single Object Detection',
            self.engine,
            'is_single_object_detection')
        if (self._configuration_file is not None
                and self._configuration_file.exists()):
            cv2.createButton('Store Configuration', self._update_configuration)
            cv2.createButton('Reset Configuration', self._reset_configuration)

    def _update_configuration(self, *_args):
        configuration = read_configuration_file(self._configuration_file)
        color_configuration = configuration['tracking']['color']
        color_configuration['is_single_object_detection'] = \
            bool(self.engine.is_single_object_detection)
        color_configuration['min_hsv'] = list(map(int, self.engine.min_hsv))
        color_configuration['max_hsv'] = list(map(int, self.engine.max_hsv))
        save_configuration_file(self._configuration_file, configuration)

    def _reset_configuration(self, *_args):
        configuration = read_configuration_file(self._configuration_file)
        color_configuration = configuration['tracking']['color']

        min_h, min_s, min_v = color_configuration['min_hsv']
        self.engine.min_hsv[0] = min_h
        cv2.setTrackbarPos('MIN_H', self._window_title, min_h)
        self.engine.min_hsv[1] = min_s
        cv2.setTrackbarPos('MIN_S', self._window_title, min_s)
        self.engine.min_hsv[2] = min_v
        cv2.setTrackbarPos('MIN_V', self._window_title, min_v)

        max_h, max_s, max_v = color_configuration['max_hsv']
        self.engine.max_hsv[0] = max_h
        cv2.setTrackbarPos('MAX_H', self._window_title, max_h)
        self.engine.max_hsv[1] = max_s
        cv2.setTrackbarPos('MAX_S', self._window_title, max_s)
        self.engine.max_hsv[2] = max_v
        cv2.setTrackbarPos('MAX_V', self._window_title, max_v)

    def _update_minimum_contour_radius(self, value):
        self.engine.minimum_contour_size = value

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
        if self.engine.mask_ui is not None:
            cv2.imshow('Mask',
                       cv2.cvtColor(self.engine.mask_ui, cv2.COLOR_RGB2BGR))
        else:
            logger.error('Mask is None')
