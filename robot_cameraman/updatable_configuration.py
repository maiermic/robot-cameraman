from pathlib import Path
from typing import Optional, List

from robot_cameraman.configuration import read_configuration_file
from robot_cameraman.detection_engine.color import ColorDetectionEngine
from robot_cameraman.image_detection import DetectionEngine


class UpdatableConfiguration:
    def __init__(
            self,
            detection_engine: DetectionEngine,
            configuration_file: Optional[Path] = None):
        self.detection_engine = detection_engine
        self.configuration_file = configuration_file
        self.configuration = read_configuration_file(configuration_file)

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
