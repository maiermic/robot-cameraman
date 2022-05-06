import logging
from logging import Logger

import cv2
from typing_extensions import Protocol

from robot_cameraman.camera_controller import SpeedManager
from robot_cameraman.tracking import CameraSpeeds

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


class ShowSpeedsInStatusBar(UserInterface):
    _pan_speed_manager: SpeedManager
    _tilt_speed_manager: SpeedManager
    _camera_speeds: CameraSpeeds

    def __init__(
            self,
            pan_speed_manager: SpeedManager,
            tilt_speed_manager: SpeedManager,
            camera_speeds: CameraSpeeds):
        self._pan_speed_manager = pan_speed_manager
        self._tilt_speed_manager = tilt_speed_manager
        self._camera_speeds = camera_speeds

    def open(self) -> None:
        pass

    def update(self) -> None:
        pan_speed = float(self._pan_speed_manager.current_speed)
        tilt_speed = float(self._tilt_speed_manager.current_speed)
        zoom_speed = self._camera_speeds.zoom_speed
        zoom_speed_str = \
            'in' if zoom_speed > 0 else 'out' if zoom_speed < 0 else 'no'
        cv2.displayStatusBar(
            'Robot Cameraman',
            f"pan: {pan_speed :3.2}, "
            f"tilt: {tilt_speed :3.2}, "
            f"zoom: {zoom_speed_str}")
