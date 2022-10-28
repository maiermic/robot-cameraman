import logging
from logging import Logger
from typing import Optional

import cv2
from typing_extensions import Protocol

from robot_cameraman.camera_controller import SpeedManager
from robot_cameraman.camera_speeds import ZoomSpeed, CameraSpeeds

logger: Logger = logging.getLogger(__name__)


class UserInterface(Protocol):
    def open(self) -> None:
        raise NotImplementedError

    def update(self) -> None:
        raise NotImplementedError


def create_attribute_checkbox(button_name: str, obj, attribute_name):
    """
    Create a checkbox and bind its value to the attribute of an object.
    If the checkbox is toggled, the attribute is updated.
    However, the checkbox is not updated, if the attribute is changed otherwise.

    :param button_name:
    :param obj:
    :param attribute_name:
    :return:
    """

    def on_change(value, _user_data):
        is_enabled = value == 1
        setattr(obj, attribute_name, is_enabled)
        state = 'enabled' if is_enabled else 'disabled'
        logger.debug(f'{button_name}: {state}')

    cv2.createButton(
        button_name,
        on_change,
        None,
        cv2.QT_CHECKBOX,
        1 if getattr(obj, attribute_name) else 0)


class StatusBar(UserInterface):
    text: str
    _pan_speed_manager: SpeedManager
    _tilt_speed_manager: SpeedManager
    _camera_speeds: CameraSpeeds
    _zoom_ratio: Optional[float]
    _zoom_index: Optional[int]

    def __init__(
            self,
            pan_speed_manager: SpeedManager,
            tilt_speed_manager: SpeedManager,
            camera_speeds: CameraSpeeds):
        self.text = ''
        self._pan_speed_manager = pan_speed_manager
        self._tilt_speed_manager = tilt_speed_manager
        self._camera_speeds = camera_speeds
        self._zoom_ratio = None
        self._zoom_index = None

    def open(self) -> None:
        pass

    def update_zoom_ratio(self, zoom_ratio: float):
        self._zoom_ratio = zoom_ratio

    def update_zoom_index(self, zoom_index: int):
        self._zoom_index = zoom_index

    def update(self) -> None:
        pan_speed = float(self._pan_speed_manager.current_speed)
        tilt_speed = float(self._tilt_speed_manager.current_speed)
        zoom_speed_str = {
            ZoomSpeed.ZOOM_IN_FAST: 'zoom in fast',
            ZoomSpeed.ZOOM_IN_SLOW: 'zoom in slow',
            ZoomSpeed.ZOOM_STOPPED: 'zoom stopped',
            ZoomSpeed.ZOOM_OUT_SLOW: 'zoom out slow',
            ZoomSpeed.ZOOM_OUT_FAST: 'zoom out fast',
        }[self._camera_speeds.zoom_speed]
        zoom_ratio = ('?' if self._zoom_ratio is None
                      else f'{self._zoom_ratio:4.1f}')
        zoom_index = ('?' if self._zoom_index is None
                      else f'{self._zoom_index:2}')
        self.text = f"pan: {pan_speed :3.2}, " \
                    f"tilt: {tilt_speed :3.2}, " \
                    f"zoom-ratio: {zoom_ratio}, " \
                    f"zoom-index: {zoom_index}, " \
                    f"{zoom_speed_str}"
        cv2.displayStatusBar('Robot Cameraman', self.text)
