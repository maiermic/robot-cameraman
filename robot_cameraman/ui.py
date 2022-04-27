import logging
from logging import Logger

import cv2
from typing_extensions import Protocol

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
