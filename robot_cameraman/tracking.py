import logging
from abc import abstractmethod
from dataclasses import dataclass
from logging import Logger
from typing import Tuple, Optional

import time
from typing_extensions import Protocol

from robot_cameraman.box import Box, TwoPointsBox, Point

logger: Logger = logging.getLogger(__name__)


class Destination:

    def __init__(self, image_size: Tuple[int, int], variance: int = 50) -> None:
        width, height = image_size
        x, y = width / 2, height / 2
        self.center = Point(x, y)
        self.box = Box.from_center_and_size(self.center,
                                            variance * 2,
                                            variance * 2)
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


@dataclass
class CameraSpeeds:
    pan_speed: int = 0
    tilt_speed: int = 0
    zoom_speed: int = 0

    def reset(self):
        self.pan_speed = 0
        self.tilt_speed = 0
        self.zoom_speed = 0


class TrackingStrategy(Protocol):
    @abstractmethod
    def update(
            self,
            camera_speeds: CameraSpeeds,
            target: Optional[Box],
            is_target_lost: bool) -> None:
        raise NotImplementedError


class SimpleTrackingStrategy(TrackingStrategy):
    _destination: Destination
    max_allowed_speed: int

    def __init__(self, destination: Destination, max_allowed_speed: int = 1000):
        self._destination = destination
        self.max_allowed_speed = max_allowed_speed

    def update(
            self,
            camera_speeds: CameraSpeeds,
            target: Optional[Box],
            is_target_lost: bool) -> None:
        if target is None or is_target_lost:
            return
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
            speed = round(abs_distance / 320 * self.max_allowed_speed)
            speed = min(self.max_allowed_speed, speed)
            if distance < 0:
                speed = -speed
            return int(speed)


class StopIfLostTrackingStrategy(TrackingStrategy):
    _destination: Destination
    _trackingStrategy: TrackingStrategy
    _slowDownTime: float
    _hasTargetBeenLost: bool
    _timeOfLoss: float

    def __init__(
            self,
            destination: Destination,
            tracking_strategy: TrackingStrategy,
            slow_down_time: float):
        self._destination = destination
        self._trackingStrategy = tracking_strategy
        self._slowDownTime = slow_down_time
        self._hasTargetBeenLost = False
        self._timeOfLoss = time.time()

    def update(self,
               camera_speeds: CameraSpeeds,
               target: Optional[Box],
               is_target_lost: bool) -> None:
        self._trackingStrategy.update(camera_speeds, target, is_target_lost)
        if is_target_lost:
            if not self._hasTargetBeenLost:
                self._timeOfLoss = time.time()
            else:
                delta_time = time.time() - self._timeOfLoss
                t = min(delta_time, self._slowDownTime)
                slow_down_factor = 1 - (t / self._slowDownTime)
                camera_speeds.pan_speed = int(
                    camera_speeds.pan_speed * slow_down_factor)
                camera_speeds.tilt_speed = int(
                    camera_speeds.tilt_speed * slow_down_factor)
                camera_speeds.zoom_speed = int(
                    camera_speeds.zoom_speed * slow_down_factor)
        self._hasTargetBeenLost = is_target_lost


class AlignTrackingStrategy(TrackingStrategy):
    @abstractmethod
    def is_aligned(self, target: Box) -> bool:
        raise NotImplementedError


class SimpleAlignTrackingStrategy(SimpleTrackingStrategy,
                                  AlignTrackingStrategy):
    def is_aligned(self, target: Box) -> bool:
        return self._destination.box.contains_point(target.center)


class SearchTargetStrategy(Protocol):
    @abstractmethod
    def update(self, camera_speeds: CameraSpeeds) -> None:
        raise NotImplementedError


class RotateSearchTargetStrategy(SearchTargetStrategy):
    def __init__(self, speed=200):
        self.speed = speed

    def update(self, camera_speeds: CameraSpeeds) -> None:
        camera_speeds.pan_speed = self.speed
