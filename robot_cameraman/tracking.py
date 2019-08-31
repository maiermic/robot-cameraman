import logging
from abc import abstractmethod
from dataclasses import dataclass
from logging import Logger
from typing import Tuple

import serial
from typing_extensions import Protocol

from robot_cameraman.box import Box, TwoPointsBox
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
        x_padding = 0.3 * width
        y_padding = 0.2 * height
        self.min_size_box = TwoPointsBox(0, 0, 0, 0)
        self.max_size_box = TwoPointsBox(0, 0, 0, 0)
        self.max_size_box.width = width - 2 * x_padding
        self.max_size_box.height = height - 2 * y_padding
        self.min_size_box.width = self.max_size_box.width - 2 * self.variance
        self.min_size_box.height = self.max_size_box.height - 2 * self.variance
        self.update_size_box_center(x, y)

    def update_size_box_center(self, x: float, y: float):
        self.max_size_box.x = x - self.max_size_box.width / 2
        self.max_size_box.y = y - self.max_size_box.height / 2
        self.max_size_box.center.set(x, y)

        self.min_size_box.x = x - self.min_size_box.width / 2
        self.min_size_box.y = y - self.min_size_box.height / 2
        self.min_size_box.center.set(x, y)


class CameraController:

    def __init__(
            self,
            destination: Destination,
            max_allowed_speed: int = 1000) -> None:
        self.destination = destination
        self.max_allowed_speed = max_allowed_speed
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


@dataclass
class CameraSpeeds:
    pan_speed: int = 0
    tilt_speed: int = 0
    zoom_speed: int = 0


class TrackingStrategy(Protocol):
    @abstractmethod
    def update(self, camera_speeds: CameraSpeeds, target: Box) -> None:
        raise NotImplementedError


class SimpleTrackingStrategy(TrackingStrategy):
    _destination: Destination
    _maxAllowedSpeed: int = 1000

    def __init__(self, destination: Destination):
        self._destination = destination

    def update(self, camera_speeds: CameraSpeeds, target: Box) -> None:
        tx, ty = target.center
        self._destination.update_size_box_center(tx, ty)
        dx, dy = self._destination.center
        camera_speeds.pan_speed = self._get_speed_by_distance(tx, dx)
        camera_speeds.tilt_speed = self._get_speed_by_distance(ty, dy)
        if target.height < self._destination.min_size_box.height:
            camera_speeds.zoom_speed = 200
        elif target.height > self._destination.max_size_box.height:
            camera_speeds.zoom_speed = -200
        else:
            camera_speeds.zoom_speed = 0

    def _get_speed_by_distance(self, tx: float, dx: float) -> int:
        distance = tx - dx
        abs_distance = abs(distance)
        if abs_distance < self._destination.variance:
            return 0
        else:
            speed = round(abs_distance / 32 * 100)
            speed = min(self._maxAllowedSpeed, speed)
            if distance < 0:
                speed = -speed
            return int(speed)
