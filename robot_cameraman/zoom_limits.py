from pathlib import Path
from typing import Optional

from robot_cameraman.camera_controller import CameraZoomLimitController, \
    CameraZoomRatioLimitController, CameraZoomIndexLimitController
from robot_cameraman.zoom import parse_zoom_steps, parse_zoom_ratio_index_ranges

import logging
from logging import Logger

logger: Logger = logging.getLogger(__name__)


class ZoomLimits:
    def __init__(
            self,
            camera_zoom_limit_controller: CameraZoomLimitController,
            max_zoom_ratio: float,
            min_zoom_ratio: float):
        self._camera_zoom_limit_controller = camera_zoom_limit_controller
        self._max_zoom_ratio = max_zoom_ratio
        self._min_zoom_ratio = min_zoom_ratio
        self._current_zoom_ratio = None

    def update_current_zoom_ratio(self, zoom_ratio: float):
        self._current_zoom_ratio = zoom_ratio

    def is_max_zoom_reached(self):
        if (isinstance(self._camera_zoom_limit_controller,
                       CameraZoomRatioLimitController)
                and self._camera_zoom_limit_controller.max_zoom_ratio):
            return self._camera_zoom_limit_controller.is_max_reached()
        if (isinstance(self._camera_zoom_limit_controller,
                       CameraZoomIndexLimitController)
                and self._camera_zoom_limit_controller.max_zoom_index):
            return self._camera_zoom_limit_controller.is_max_reached()
        return self._current_zoom_ratio >= self._max_zoom_ratio

    def is_min_zoom_reached(self):
        if (isinstance(self._camera_zoom_limit_controller,
                       CameraZoomRatioLimitController)
                and self._camera_zoom_limit_controller.min_zoom_ratio):
            return self._camera_zoom_limit_controller.is_min_reached()
        if (isinstance(self._camera_zoom_limit_controller,
                       CameraZoomIndexLimitController)
                and self._camera_zoom_limit_controller.min_zoom_index is not None):
            return self._camera_zoom_limit_controller.is_min_reached()
        return self._current_zoom_ratio <= self._min_zoom_ratio


def get_zoom_ratio_limits_from_configuration(
        zoom_steps_file: Optional[Path],
        zoom_ratio_index_ranges_file: Optional[Path],
) -> tuple[float, float]:
    if zoom_steps_file:
        zoom_steps = parse_zoom_steps(zoom_steps_file)
        return zoom_steps.get_min_zoom_ratio(), zoom_steps.get_max_zoom_ratio()
    if zoom_ratio_index_ranges_file:
        zoom_ratio_index_ranges = parse_zoom_ratio_index_ranges(
            zoom_ratio_index_ranges_file)
        zoom_ratios = [r.zoom_ratio for r in zoom_ratio_index_ranges]
        return min(zoom_ratios), max(zoom_ratios)

    default_zoom_limits = (1.0, 14.3)
    logger.warning(f'Default zoom limits ({default_zoom_limits}) are used,'
                   f' since no zoom configuration (e.g. zoom-steps'
                   f'  or zoom-ratio-index-ranges) is given')
    return default_zoom_limits
