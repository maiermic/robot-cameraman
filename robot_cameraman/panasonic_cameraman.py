import io
import logging
import os
import socket
import threading
import time
from logging import Logger
from typing import Optional

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import cv2
import numpy
from imutils.video import FPS

from panasonic_camera.live_view import LiveView
from robot_cameraman.annotation import ImageAnnotator, draw_destination
from robot_cameraman.cameraman_mode_manager import CameramanModeManager
from robot_cameraman.image_detection import DetectionEngine, DetectionCandidate
from robot_cameraman.object_tracking import ObjectTracker
from robot_cameraman.server import ImageContainer
from robot_cameraman.tracking import Destination

logger: Logger = logging.getLogger(__name__)


class PanasonicCameraman:
    _target_id: Optional[int] = None

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

    def run(self,
            server_image: ImageContainer,
            to_exit: threading.Event) -> None:
        self._mode_manager.start()
        fps: FPS = FPS().start()
        while not to_exit.is_set():
            try:
                try:
                    image = PIL.Image.open(io.BytesIO(self._live_view.image()))
                except socket.timeout:
                    logger.error('timeout reading live view image')
                    self._mode_manager.update()
                    continue
                assert image.size == (640, 480)
                # Perform inference and note time taken
                start_ms = time.time()
                try:
                    inference_results = self.detection_engine.detect(image)
                    target_inference_results = [
                        obj for obj in inference_results
                        if obj.label_id == self._target_label_id]
                    candidates = self._object_tracker.update(
                        target_inference_results)
                    target: Optional[DetectionCandidate] = None
                    if self._target_id is not None:
                        if self._target_id in candidates:
                            target = candidates[self._target_id]
                    else:
                        ts = candidates.items()
                        if ts:
                            (self._target_id, target) = next(iter(ts))
                            logger.debug('track target %d', self._target_id)
                    draw_destination(image, self._destination)
                    self.annotator.annotate(image, self._target_id, candidates)
                    if target:
                        self._mode_manager.update(target.bounding_box)
                    else:
                        self._mode_manager.update()
                except OSError as e:
                    logger.error(str(e))
                    pass

                server_image.image = image
                cv2_image = cv2.cvtColor(numpy.asarray(image),
                                         cv2.COLOR_RGB2BGR)
                if self._output:
                    self._output.write(cv2_image)
                if 'DISPLAY' in os.environ:
                    cv2.imshow('NCS Improved live inference', cv2_image)

                # Display the frame for 5ms, and close the window so that the
                # next frame can be displayed. Close the window if 'q' or 'Q'
                # is pressed.
                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break

                fps.update()

            # Allows graceful exit using ctrl-c (handy for headless mode).
            except KeyboardInterrupt:
                break

        fps.stop()
        self._mode_manager.stop()
        logger.debug("Elapsed time: " + str(fps.elapsed()))
        logger.debug("Approx FPS: :" + str(fps.fps()))

        cv2.destroyAllWindows()
