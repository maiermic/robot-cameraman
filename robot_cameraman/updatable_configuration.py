from pathlib import Path
from typing import Optional, List, Union

from robot_cameraman.camera_controller import CameraAngleLimitController, \
    CameraZoomRatioLimitController, CameraZoomIndexLimitController
from robot_cameraman.cameraman_mode_manager import CameramanModeManager
from robot_cameraman.configuration import read_configuration_file
from robot_cameraman.detection_engine.color import ColorDetectionEngine
from robot_cameraman.image_detection import DetectionEngine
from robot_cameraman.tracking import SearchTargetStrategy, \
    StaticSearchTargetStrategy
from robot_cameraman.zoom import ZoomRatioIndexRange


class UpdatableConfiguration:
    def __init__(
            self,
            detection_engine: DetectionEngine,
            cameraman_mode_manager: CameramanModeManager,
            camera_zoom_limit_controller: Union[
                CameraZoomIndexLimitController, CameraZoomRatioLimitController],
            camera_angle_limit_controller: CameraAngleLimitController,
            configuration_file: Optional[Path],
            camera_zoom_ratio_index_ranges: Optional[List[ZoomRatioIndexRange]],
            search_target_strategy: SearchTargetStrategy):
        self.detection_engine = detection_engine
        self.cameraman_mode_manager = cameraman_mode_manager
        self.camera_zoom_limit_controller = camera_zoom_limit_controller
        self.camera_angle_limit_controller = camera_angle_limit_controller
        self.search_target_strategy = search_target_strategy
        self.configuration_file = configuration_file
        self.configuration = read_configuration_file(configuration_file)
        if 'limits' not in self.configuration:
            min_pan = self.camera_angle_limit_controller.min_pan_angle
            max_pan = self.camera_angle_limit_controller.max_pan_angle
            min_tilt = self.camera_angle_limit_controller.min_tilt_angle
            max_tilt = self.camera_angle_limit_controller.max_tilt_angle
            min_zoom_ratio = getattr(self.camera_zoom_limit_controller,
                                     'min_zoom_ratio',
                                     None)
            max_zoom_ratio = getattr(self.camera_zoom_limit_controller,
                                     'max_zoom_ratio',
                                     None)
            min_zoom_index = getattr(self.camera_zoom_limit_controller,
                                     'min_zoom_index',
                                     None)
            max_zoom_index = getattr(self.camera_zoom_limit_controller,
                                     'max_zoom_index',
                                     None)
            self.configuration['limits'] = {
                'areLimitsAppliedInManualMode':
                    cameraman_mode_manager.are_limits_applied_in_manual_mode,
                'pan': None if min_pan is None else [min_pan, max_pan],
                'tilt': None if min_tilt is None else [min_tilt, max_tilt],
                'zoom': (None if min_zoom_ratio is None
                         else [min_zoom_ratio, max_zoom_ratio]),
                'zoomIndex': (None if min_zoom_index is None
                              else [min_zoom_index, max_zoom_index]),
            }
        if ('searchTarget' not in self.configuration
                and isinstance(self.search_target_strategy,
                               StaticSearchTargetStrategy)):
            self.configuration['searchTarget'] = {
                'isZoomWhileRotating':
                    self.search_target_strategy.is_zoom_while_rotating,
                'pan': self.search_target_strategy._target_pan_angle or 0,
                'tilt': self.search_target_strategy._target_tilt_angle or 0,
            }
            if camera_zoom_ratio_index_ranges is None:
                self.configuration['searchTarget']['zoomRatio'] = \
                    self.search_target_strategy._target_zoom_ratio or 1.0
            else:
                self.configuration['searchTarget']['zoomIndex'] = \
                    self.search_target_strategy._target_zoom_index or 0
        self.configuration['camera'] = {
            'zoomRatioIndexRanges': camera_zoom_ratio_index_ranges,
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
        if 'zoomIndex' in limits:
            zoom_limit = limits['zoomIndex']
            minimum, maximum = (
                None, None) if zoom_limit is None else zoom_limit
            self.camera_zoom_limit_controller.min_zoom_index = minimum
            self.camera_zoom_limit_controller.max_zoom_index = maximum
            self.configuration['limits']['zoomIndex'] = zoom_limit

    def update_search_target(self, search_target):
        if 'isZoomWhileRotating' in search_target:
            is_zoom_while_rotating = search_target['isZoomWhileRotating']
            self.cameraman_mode_manager.is_zoom_while_rotating = \
                is_zoom_while_rotating
            self.configuration['searchTarget']['isZoomWhileRotating'] = \
                is_zoom_while_rotating
        pan = None
        if 'pan' in search_target:
            pan = search_target['pan']
            self.configuration['searchTarget']['pan'] = pan
        tilt = None
        if 'tilt' in search_target:
            tilt = search_target['tilt']
            self.configuration['searchTarget']['tilt'] = tilt
        zoom_index = None
        if 'zoomIndex' in search_target:
            zoom_index = search_target['zoomIndex']
            self.configuration['searchTarget']['zoomIndex'] = zoom_index
        zoom_ratio = None
        if 'zoomRatio' in search_target:
            zoom_ratio = search_target['zoomRatio']
            self.configuration['searchTarget']['zoomRatio'] = zoom_ratio
        if isinstance(self.search_target_strategy,
                      StaticSearchTargetStrategy):
            self.search_target_strategy.update_target(
                pan_angle=pan,
                tilt_angle=tilt,
                zoom_index=zoom_index,
                zoom_ratio=zoom_ratio)
