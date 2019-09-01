import logging
from logging import Logger

import serial

from simplebgc.serial_example import rotate_gimbal

logger: Logger = logging.getLogger(__name__)


class CameraController:
    yaw_speed: int = 0

    def is_camera_moving(self) -> bool:
        return self.yaw_speed != 0

    def stop(self) -> None:
        self.rotate(0)

    def rotate(self, yaw_speed: int) -> None:
        if self.yaw_speed != yaw_speed:
            try:
                logger.debug('rotate gimbal with speed {}'.format(yaw_speed))
                rotate_gimbal(yaw_speed)
                self.yaw_speed = yaw_speed
            except serial.serialutil.SerialException:
                logger.error('caught SerialException')
