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
from robot_cameraman.image_detection import DetectionEngine
from robot_cameraman.server import ImageContainer
from robot_cameraman.tracking import Destination, CameraController, \
    SimpleTrackingStrategy, CameraSpeeds, TrackingStrategy

logger: Logger = logging.getLogger(__name__)


class PanasonicCameraman:

    def __init__(
            self,
            live_view: LiveView,
            annotator: ImageAnnotator,
            detection_engine: DetectionEngine,
            output: Optional[cv2.VideoWriter]) -> None:
        self._live_view = live_view
        self.annotator = annotator
        self.detection_engine = detection_engine
        self._output = output

    def run(self,
            server_image: ImageContainer,
            to_exit: threading.Event) -> None:
        # Use imutils to count Frames Per Second (FPS)
        fps: FPS = FPS().start()
        destination: Optional[Destination] = None
        camera_controller: Optional[CameraController] = None
        tracking_strategy: Optional[TrackingStrategy] = None
        camera_speeds: CameraSpeeds = CameraSpeeds()
        while not to_exit.is_set():
            try:
                try:
                    image = PIL.Image.open(io.BytesIO(self._live_view.image()))
                except socket.timeout:
                    logger.error('timeout reading live view image')
                    continue
                if destination is None:
                    destination = Destination(image.size, variance=20)
                    camera_controller = CameraController(destination)
                    tracking_strategy = SimpleTrackingStrategy(destination)
                # Perform inference and note time taken
                start_ms = time.time()
                try:
                    inference_results = self.detection_engine.detect(image)
                    draw_destination(image, destination)
                    self.annotator.annotate(image, inference_results)
                    target = self.annotator.target
                    if target is None:
                        # search target
                        camera_controller.rotate(500)
                    else:
                        tracking_strategy.update(camera_speeds, target.box)
                        camera_controller.rotate(camera_speeds.pan_speed)
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

        if camera_controller:
            logger.debug('Stop camera')
            camera_controller.stop()
        fps.stop()
        logger.debug("Elapsed time: " + str(fps.elapsed()))
        logger.debug("Approx FPS: :" + str(fps.fps()))

        cv2.destroyAllWindows()
