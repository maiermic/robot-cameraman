from robot_cameraman.camera_controller import CameraZoomLimitController, \
    CameraZoomRatioLimitController, CameraZoomIndexLimitController


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
