from pathlib import Path
from typing import Optional, List

from robot_cameraman.camera_controller import CameraAngleLimitController, \
    CameraZoomLimitController
from robot_cameraman.cameraman_mode_manager import CameramanModeManager
from robot_cameraman.configuration import read_configuration_file
from robot_cameraman.detection_engine.color import ColorDetectionEngine
from robot_cameraman.image_detection import DetectionEngine


class UpdatableConfiguration:
    def __init__(
            self,
            detection_engine: DetectionEngine,
            cameraman_mode_manager: CameramanModeManager,
            camera_zoom_limit_controller: CameraZoomLimitController,
            camera_angle_limit_controller: CameraAngleLimitController,
            configuration_file: Optional[Path] = None):
        self.detection_engine = detection_engine
        self.cameraman_mode_manager = cameraman_mode_manager
        self.camera_zoom_limit_controller = camera_zoom_limit_controller
        self.camera_angle_limit_controller = camera_angle_limit_controller
        self.configuration_file = configuration_file
        self.configuration = read_configuration_file(configuration_file)
        if 'limits' not in self.configuration:
            min_pan = self.camera_angle_limit_controller.min_pan_angle
            max_pan = self.camera_angle_limit_controller.max_pan_angle
            min_tilt = self.camera_angle_limit_controller.min_tilt_angle
            max_tilt = self.camera_angle_limit_controller.max_tilt_angle
            min_zoom = self.camera_zoom_limit_controller.min_zoom_ratio
            max_zoom = self.camera_zoom_limit_controller.max_zoom_ratio
            self.configuration['limits'] = {
                'areLimitsAppliedInManualMode':
                    cameraman_mode_manager.are_limits_applied_in_manual_mode,
                'pan': None if min_pan is None else [min_pan, max_pan],
                'tilt': None if min_tilt is None else [min_tilt, max_tilt],
                'zoom': None if min_zoom is None else [min_zoom, max_zoom],
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
        if 'areLimitsAppliedInManualMode' in limits:
            applied_in_manual_mode = limits['areLimitsAppliedInManualMode']
            self.cameraman_mode_manager.are_limits_applied_in_manual_mode = \
                applied_in_manual_mode
            self.configuration['limits']['areLimitsAppliedInManualMode'] = \
                applied_in_manual_mode
        if 'pan' in limits:
            pan_limit = limits['pan']
            minimum, maximum = (None, None) if pan_limit is None else pan_limit
            self.camera_angle_limit_controller.min_pan_angle = minimum
            self.camera_angle_limit_controller.max_pan_angle = maximum
            self.configuration['limits']['pan'] = pan_limit
        if 'tilt' in limits:
            tilt_limit = limits['tilt']
            minimum, maximum = (
                None, None) if tilt_limit is None else tilt_limit
            self.camera_angle_limit_controller.min_tilt_angle = minimum
            self.camera_angle_limit_controller.max_tilt_angle = maximum
            self.configuration['limits']['tilt'] = tilt_limit
        if 'zoom' in limits:
            zoom_limit = limits['zoom']
            minimum, maximum = (
                None, None) if zoom_limit is None else zoom_limit
            self.camera_zoom_limit_controller.min_zoom_ratio = minimum
            self.camera_zoom_limit_controller.max_zoom_ratio = maximum
            self.configuration['limits']['zoom'] = zoom_limit
