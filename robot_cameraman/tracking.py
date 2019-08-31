import logging
from logging import Logger
from typing import Tuple

import serial

from robot_cameraman.box import Box
from simplebgc.serial_example import rotate_gimbal

logger: Logger = logging.getLogger(__name__)


class Destination:

    def __init__(self, image_size: Tuple[int, int], variance: int = 50) -> None:
        width, height = image_size
        x, y = width / 2, height / 2
        self.center = (x, y)
        self.box = (x - variance, 0,
                    x + variance, height)
        self.variance = variance


class CameraController:

    def __init__(
            self,
            destination: Destination,
            max_allowed_speed: int = 1000) -> None:
        self.destination = destination
        self.max_allowed_speed = max_allowed_speed
        self.search_speed = round(max_allowed_speed / 2)
        self.yaw_speed = 0

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

    def update(self, target_box: Box) -> None:
        if target_box is None:
            self.search_target()
        else:
            self.move_to_target(target_box)

    def move_to_target(self, target_box: Box) -> None:
        tx, ty = target_box.center
        dx, dy = self.destination.center
        distance = tx - dx
        # print(distance)
        abs_distance = abs(distance)
        if abs_distance < self.destination.variance:
            if self.is_camera_moving():
                self.stop()
        else:
            # TODO check speed range of 2s is -32,768 to 32,767
            # image_width / speed_steps = 640 / 20 = 32
            # max_allowed_speed / speed_steps = 1000 / 20 = 100
            speed = round(abs_distance / 32 * 100)
            speed = min(self.max_allowed_speed, speed)
            if distance < 0:
                speed = -speed
            self.rotate(int(speed))

    def rotate_right(self) -> None:
        self.rotate(100)

    def rotate_left(self) -> None:
        self.rotate(-100)

    def search_target(self) -> None:
        self.rotate(self.search_speed)
