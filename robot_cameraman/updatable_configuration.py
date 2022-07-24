from pathlib import Path
from typing import Optional, List

from robot_cameraman.camera_controller import CameraAngleLimitController
from robot_cameraman.configuration import read_configuration_file
from robot_cameraman.detection_engine.color import ColorDetectionEngine
from robot_cameraman.image_detection import DetectionEngine


class UpdatableConfiguration:
    def __init__(
            self,
            detection_engine: DetectionEngine,
            camera_angle_limit_controller: CameraAngleLimitController,
            configuration_file: Optional[Path] = None):
        self.detection_engine = detection_engine
        self.camera_angle_limit_controller = camera_angle_limit_controller
        self.configuration_file = configuration_file
        self.configuration = read_configuration_file(configuration_file)
        if 'limits' not in self.configuration:
            self.configuration['limits'] = {
                'pan': None,
                'tilt': None,
            }

    def update_tracking_color(
            self,
            min_hsv: Optional[List[int]] = None,
            max_hsv: Optional[List[int]] = None):
        if isinstance(self.detection_engine, ColorDetectionEngine):
            if min_hsv is not None:
                self.detection_engine.min_hsv[:] = min_hsv
                self.configuration['tracking']['color']['min_hsv'] = min_hsv
            if max_hsv is not None:
                self.detection_engine.max_hsv[:] = max_hsv
                self.configuration['tracking']['color']['max_hsv'] = max_hsv

    def update_limits(self, limits):
        if 'pan' in limits:
            pan_limit = limits['pan']
            minimum, maximum = (None, None) if pan_limit is None else pan_limit
            self.camera_angle_limit_controller.min_pan_angle = minimum
            self.camera_angle_limit_controller.max_pan_angle = maximum
            self.configuration['limits']['pan'] = pan_limit
        if 'tilt' in limits:
            tilt_limit = limits['tilt']
            minimum, maximum = (None, None) if tilt_limit is None else tilt_limit
            self.camera_angle_limit_controller.min_tilt_angle = minimum
            self.camera_angle_limit_controller.max_tilt_angle = maximum
            self.configuration['limits']['tilt'] = tilt_limit
