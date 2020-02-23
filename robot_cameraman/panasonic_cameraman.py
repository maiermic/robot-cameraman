import io
import logging
import os
import socket
import threading
from logging import Logger
from typing import Optional, Iterable

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFile
import PIL.ImageFont
import cv2
import numpy
import time
from imutils.video import FPS

from panasonic_camera.live_view import LiveView
from robot_cameraman.annotation import ImageAnnotator, draw_destination
from robot_cameraman.box import Box
from robot_cameraman.cameraman_mode_manager import CameramanModeManager
from robot_cameraman.candidate_filter import filter_intersections
from robot_cameraman.image_detection import DetectionEngine, DetectionCandidate
from robot_cameraman.object_tracking import ObjectTracker
from robot_cameraman.server import ImageContainer
from robot_cameraman.tracking import Destination

logger: Logger = logging.getLogger(__name__)


class PanasonicCameraman:
    _target_id: Optional[int] = None
    _target_box: Optional[Box] = None

    def __init__(
            self,
            live_view: LiveView,
            annotator: ImageAnnotator,
            detection_engine: DetectionEngine,
            destination: Destination,
            mode_manager: CameramanModeManager,
            object_tracker: ObjectTracker,
            target_label_id: int,
            output: Optional[cv2.VideoWriter]) -> None:
        self._live_view = live_view
        self.annotator = annotator
        self.detection_engine = detection_engine
        self._destination = destination
        self._mode_manager = mode_manager
        self._object_tracker = object_tracker
        self._target_label_id = target_label_id
        self._output = output

    def _is_target_id_registered(self) -> bool:
        return (self._target_id is not None
                and self._object_tracker.is_registered(self._target_id))

    def run(self,
            server_image: ImageContainer,
            to_exit: threading.Event) -> None:
        # Parts at the end of the live view image are sometimes not received.
        # These truncated images cause an exception in the detection engine,
        # if the following option is not enabled. In the cases observed so far,
        # only a small part of the image is missing. Hence, we still try to
        # detect the target in the transferred image.
        PIL.ImageFile.LOAD_TRUNCATED_IMAGES = True
        self._mode_manager.start()
        fps: FPS = FPS().start()
        frame_counter = 0
        while not to_exit.is_set():
            try:
                try:
                    image = PIL.Image.open(io.BytesIO(self._live_view.image()))
                except (socket.timeout, OSError) as e:
                    logger.error(f'error reading live view image: {e}')
                    self._mode_manager.update(self._target_box,
                                              is_target_lost=True)
                    self.handle_keyboard_input(to_exit)
                    continue
                frame_counter += 1
                logger.debug(f'frame {frame_counter}')
                assert image.size == (640, 480), image.size
                # Perform inference and note time taken
                start_ms = time.time()
                try:
                    inference_results = self.detection_engine.detect(image)
                    target_inference_results = [
                        obj for obj in inference_results
                        if obj.label_id == self._target_label_id]
                    self.log_candidates('candidates', target_inference_results)
                    filtered_candidates = filter_intersections(
                        target_inference_results)
                    self.log_candidates('filtered_candidates',
                                        filtered_candidates)
                    candidates = self._object_tracker.update(
                        filtered_candidates)
                    is_target_lost = False
                    if self._is_target_id_registered():
                        if self._target_id in candidates:
                            target = candidates[self._target_id]
                            self._target_box = target.bounding_box
                    else:
                        ts = candidates.items()
                        if ts:
                            (self._target_id, target) = next(iter(ts))
                            self._target_box = target.bounding_box
                            logger.debug('track target %d', self._target_id)
                        else:
                            is_target_lost = True
                            self._target_box = None
                    # The mode manager updates the destination as a side effect.
                    # The destination has to be drawn afterwards.
                    self._mode_manager.update(self._target_box, is_target_lost)
                    draw_destination(image, self._destination)
                    self.annotator.annotate(image, self._target_id, candidates,
                                            self._mode_manager.mode_name)
                except OSError as e:
                    logger.error(e)

                server_image.image = image
                cv2_image = cv2.cvtColor(numpy.asarray(image),
                                         cv2.COLOR_RGB2BGR)
                if self._output:
                    self._output.write(cv2_image)
                if 'DISPLAY' in os.environ:
                    cv2.imshow('Robot Cameraman', cv2_image)

                self.handle_keyboard_input(to_exit)

                fps.update()

            # Allows graceful exit using ctrl-c (handy for headless mode).
            except KeyboardInterrupt:
                break

        fps.stop()
        self._mode_manager.stop()
        logger.debug("Elapsed time: " + str(fps.elapsed()))
        logger.debug("Approx FPS: :" + str(fps.fps()))

        cv2.destroyAllWindows()

    def handle_keyboard_input(self, to_exit):
        # Display the frame for 5ms, and close the window so that the
        # next frame can be displayed. Close the window if 'q' or 'Q'
        # is pressed.
        key = cv2.waitKey(5) & 0xFF
        if key == ord('q'):
            logger.debug('key pressed to quit')
            to_exit.set()
        elif key == ord('t'):
            logger.debug('start tracking')
            self._mode_manager.tracking_mode()
        elif key == ord('i'):
            logger.debug('manually tilt up')
            self._mode_manager.manual_mode()
            self._mode_manager.manual_tilt(-100)
        elif key == ord('k'):
            logger.debug('manually tilt down')
            self._mode_manager.manual_mode()
            self._mode_manager.manual_tilt(100)
        elif key == ord('j'):
            logger.debug('manually rotate left')
            self._mode_manager.manual_mode()
            self._mode_manager.manual_rotate(-100)
        elif key == ord('l'):
            logger.debug('manually rotate right')
            self._mode_manager.manual_mode()
            self._mode_manager.manual_rotate(100)
        elif key == ord('-'):
            logger.debug('manually zoom out')
            self._mode_manager.manual_mode()
            self._mode_manager.manual_zoom(-200)
        elif key == ord('+'):
            logger.debug('manually zoom in')
            self._mode_manager.manual_mode()
            self._mode_manager.manual_zoom(200)
        elif self._mode_manager.is_manual_mode() and key == ord('o'):
            logger.debug('manually stop')
            self._mode_manager.stop_camera()

    @staticmethod
    def log_candidates(
            candidates_name: str,
            candidates: Iterable[DetectionCandidate]):
        logger.debug(f'  {candidates_name}:')
        for c in candidates:
            bb = c.bounding_box
            logger.debug(f'    ({bb.x:3.0f}, {bb.y:3.0f},'
                         f' {bb.width:3.0f}, {bb.height:3.0f})')
