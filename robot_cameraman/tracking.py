import logging
import time
from abc import abstractmethod
from enum import Enum, auto
from logging import Logger
from typing import Optional

import numpy
from typing_extensions import Protocol

from robot_cameraman.angle import get_delta_angle_clockwise, get_angle_distance
from robot_cameraman.box import Box, TwoPointsBox, Point
from robot_cameraman.camera_controller import CameraZoomLimitController, \
    CameraAngleLimitController, CameraZoomIndexLimitController, \
    CameraZoomRatioLimitController
from robot_cameraman.camera_speeds import ZoomSpeed, CameraSpeeds
from robot_cameraman.gimbal import Angles
from robot_cameraman.live_view import ImageSize

logger: Logger = logging.getLogger(__name__)


class Destination:

    def __init__(self, image_size: ImageSize, variance: int = 50) -> None:
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
    _image_size: ImageSize
    max_allowed_speed: float

    def __init__(
            self,
            destination: Destination,
            image_size: ImageSize,
            max_allowed_speed: float = 1000):
        self._destination = destination
        self._image_size = image_size
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
        camera_speeds.pan_speed = \
            self._get_speed_by_distance(tx, dx, self._image_size.width)
        # Tilt speed has to be inverted, since the origin of the coordinate
        # system of the image is in the top left corner. For example, if the
        # target is at the top of the image, its y-coordinate is 0.
        # The y-coordinate of the destination is positive.
        # _get_speed_by_distance returns a negative speed,
        # but CameraSpeeds expects a positive tilt speed to move the camera
        # upwards (to the target). Therefore, the returned speed is inverted.
        camera_speeds.tilt_speed = \
            -self._get_speed_by_distance(ty, dy, self._image_size.height)
        self._update_zoom_speed(camera_speeds, target)

    def _update_zoom_speed(self, camera_speeds, target):
        if target.height < self._destination.min_size_box.height:
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_IN_FAST
        elif target.height > self._destination.max_size_box.height:
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_OUT_FAST
        else:
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED

    def _get_speed_by_distance(
            self, target: float, destination: float, size: int) -> float:
        distance = target - destination
        abs_distance = abs(distance)
        if abs_distance < self._destination.variance:
            return 0
        else:
            speed = abs_distance / (size / 2) * self.max_allowed_speed
            speed = min(self.max_allowed_speed, speed)
            if distance < 0:
                speed = -speed
            return speed


class TrackingStrategyRotationMode(Enum):
    STOP = auto()
    """Stop rotation, when distance of object to center is smaller than
    the variance."""

    LINEAR = auto()
    "Rotation speed increases linear based on distance of object to center."

    QUADRATIC = auto()
    "Rotation speed increases quadratic based on distance of object to center."

    QUADRATIC_TO_LINEAR = auto()
    """Rotation speed increases quadratic based on distance of object to center,
     when distance of object to center is smaller than the variance.
     Otherwise, rotation speed increases linear based on distance of object
     to center."""


class TrackingStrategyZoomInMode(Enum):
    SLOW = auto()
    "Zoom in slowly when threshold (based on variance) is reached."

    FAST = auto()
    "Zoom in fast when threshold (based on variance) is reached."

    SLOW_WHEN_ALIGNED = auto()
    """Zoom in slowly when threshold (based on variance) is reached
    and target is vertically and horizontally aligned.
    """

    FAST_WHEN_ALIGNED = auto()
    """Zoom in fast when threshold (based on variance) is reached
    and target is vertically and horizontally aligned.
    """

    GRADUALLY = auto()
    """When threshold (based on variance) is reached,
    zoom in faster the nearer the target is to the destination center, i.e.
     
    - zoom in fast when target is vertically and horizontally aligned,
    - zoom in slowly when target is mostly vertically and horizontally aligned,
      i.e. the distance of the target box to the edge of the live view is
      at least 1.5 times its
      
      - width (distance to left/right edge) or
      - height (distance to top/bottom edge)
    - otherwise, do not zoom in
    """

    # TODO it might be beneficial to gradually zoom based on predicting the
    #  size of the target after zooming, i.e. don't just use a magic constant
    #  as mode GRADUALLY, but predict the size change based on zoom ratio or
    #  DistanceEstimator

    # TODO add mode similar to GRADUALLY, but with configurable ranges,
    #  e.g. zoom in slow, when distance is at least times 2.0 times its
    #  width/height, and fast, when distance is at least times 4.0 times its
    #  width/height. Different factors might be used for width and height.


class ConfigurableTrackingStrategy(SimpleTrackingStrategy):
    rotation_mode: TrackingStrategyRotationMode
    zoom_in_mode: TrackingStrategyZoomInMode

    def __init__(
            self,
            destination: Destination,
            image_size: ImageSize,
            max_allowed_speed: float = 1000):
        super().__init__(destination, image_size, max_allowed_speed)
        self.rotation_mode = TrackingStrategyRotationMode.QUADRATIC_TO_LINEAR
        self.zoom_in_mode = TrackingStrategyZoomInMode.SLOW_WHEN_ALIGNED

    def _is_xy_aligned(self, target: Box) -> bool:
        return self._destination.box.contains_point(target.center)

    def _is_in_slow_zoom_in_range(self, target: Box):
        slow_zoom_in_range = Box.from_center_and_size(
            self._destination.center,
            self._image_size.width - 3 * target.width,
            self._image_size.height - 3 * target.height)
        return slow_zoom_in_range.intersect(target).area() > 0

    def _update_zoom_speed(self, camera_speeds, target: Box):
        if target.height < self._destination.min_size_box.height:
            camera_speeds.zoom_speed = self._zoom_in(target)
        elif target.height > self._destination.max_size_box.height:
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_OUT_FAST
        else:
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED

    def _zoom_in(self, target):
        if self.zoom_in_mode is TrackingStrategyZoomInMode.SLOW:
            return ZoomSpeed.ZOOM_IN_SLOW
        if self.zoom_in_mode is TrackingStrategyZoomInMode.FAST:
            return ZoomSpeed.ZOOM_IN_FAST
        if self.zoom_in_mode is TrackingStrategyZoomInMode.SLOW_WHEN_ALIGNED:
            if self._is_xy_aligned(target):
                return ZoomSpeed.ZOOM_IN_SLOW
            else:
                return ZoomSpeed.ZOOM_STOPPED
        if self.zoom_in_mode is TrackingStrategyZoomInMode.FAST_WHEN_ALIGNED:
            if self._is_xy_aligned(target):
                return ZoomSpeed.ZOOM_IN_FAST
            else:
                return ZoomSpeed.ZOOM_STOPPED
        if self.zoom_in_mode is TrackingStrategyZoomInMode.GRADUALLY:
            if self._is_xy_aligned(target):
                return ZoomSpeed.ZOOM_IN_FAST
            elif self._is_in_slow_zoom_in_range(target):
                return ZoomSpeed.ZOOM_IN_SLOW
            else:
                return ZoomSpeed.ZOOM_STOPPED
        logger.warning(f"unhandled zoom in mode {self.zoom_in_mode}")
        return ZoomSpeed.ZOOM_STOPPED

    def _get_speed_by_distance(
            self, target: float, destination: float, size: int) -> float:
        distance = target - destination
        abs_distance = abs(distance)
        max_distance = size / 2
        variance = self._destination.variance
        if abs_distance < variance:
            if self.rotation_mode is TrackingStrategyRotationMode.STOP:
                return 0
            if (self.rotation_mode
                    is TrackingStrategyRotationMode.QUADRATIC_TO_LINEAR):
                return (self.max_allowed_speed * distance * abs_distance) \
                       / (variance * max_distance)
        percentage_distance = abs_distance / max_distance
        if self.rotation_mode is TrackingStrategyRotationMode.QUADRATIC:
            speed = (percentage_distance ** 2) * self.max_allowed_speed
        else:
            speed = percentage_distance * self.max_allowed_speed
        speed = min(self.max_allowed_speed, speed)
        if distance < 0:
            speed = -speed
        return speed


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
                camera_speeds.pan_speed = \
                    camera_speeds.pan_speed * slow_down_factor
                camera_speeds.tilt_speed = \
                    camera_speeds.tilt_speed * slow_down_factor
                camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED
        self._hasTargetBeenLost = is_target_lost


class AlignTrackingStrategy(TrackingStrategy):
    @abstractmethod
    def is_aligned(self, target: Box) -> bool:
        raise NotImplementedError


class SimpleAlignTrackingStrategy(SimpleTrackingStrategy,
                                  AlignTrackingStrategy):
    def is_aligned(self, target: Box) -> bool:
        return self._destination.box.contains_point(target.center)


class ConfigurableAlignTrackingStrategy(ConfigurableTrackingStrategy,
                                        AlignTrackingStrategy):

    def _is_zoom_aligned(self, target: Box) -> bool:
        min_height = self._destination.min_size_box.height
        max_height = self._destination.max_size_box.height
        return min_height <= target.height <= max_height

    def is_aligned(self, target: Box) -> bool:
        return self._is_xy_aligned(target) and self._is_zoom_aligned(target)


class ConfigurableTrackingStrategyUi:

    def __init__(
            self,
            tracking_strategy: ConfigurableTrackingStrategy,
            align_strategy: ConfigurableAlignTrackingStrategy) -> None:
        self._tracking_strategy = tracking_strategy
        self._align_strategy = align_strategy

    def on_change(self, _value, rotation_mode):
        logger.debug(f"change rotation mode to: {str(rotation_mode)}")
        self._tracking_strategy.rotation_mode = rotation_mode
        self._align_strategy.rotation_mode = rotation_mode

    def create_radio_button(
            self,
            name: str,
            value: TrackingStrategyRotationMode,
            initial_state=0):
        import cv2
        cv2.createButton(
            name,
            self.on_change,
            userData=value,
            buttonType=cv2.QT_RADIOBOX,
            initialButtonState=initial_state)

    def open(self) -> None:
        self.create_radio_button('Stop', TrackingStrategyRotationMode.STOP)
        self.create_radio_button(
            'Linear', TrackingStrategyRotationMode.LINEAR, initial_state=1)
        self.create_radio_button(
            'Quadratic', TrackingStrategyRotationMode.QUADRATIC)
        self.create_radio_button(
            'Quadratic-To-Linear',
            TrackingStrategyRotationMode.QUADRATIC_TO_LINEAR)

    def update(self) -> None:
        pass


class SearchTargetStrategy(Protocol):
    @abstractmethod
    def update(self, camera_speeds: CameraSpeeds) -> None:
        raise NotImplementedError


class RotateSearchTargetStrategy(SearchTargetStrategy):
    def __init__(self, speed=200):
        self.speed = speed

    def update(self, camera_speeds: CameraSpeeds) -> None:
        camera_speeds.pan_speed = self.speed


class StaticSearchTargetStrategy(SearchTargetStrategy):
    _camera_zoom_limit_controller: CameraZoomLimitController
    _camera_angle_limit_controller: CameraAngleLimitController
    _target_pan_angle: Optional[float]
    _target_tilt_angle: Optional[float]
    _target_zoom_index: Optional[int]
    _target_zoom_ratio: Optional[float]

    _current_pan_angle: Optional[float]
    _current_tilt_angle: Optional[float]
    # TODO update zoom index and ratio
    _current_zoom_index: Optional[int]
    _current_zoom_ratio: Optional[float]

    _camera_speeds: CameraSpeeds
    _is_searching: bool

    def __init__(
            self,
            pan_speed: float,
            tilt_speed: float,
            camera_zoom_limit_controller: CameraZoomLimitController,
            camera_angle_limit_controller: CameraAngleLimitController):
        self.pan_speed = pan_speed
        self.tilt_speed = tilt_speed
        self._camera_zoom_limit_controller = camera_zoom_limit_controller
        self._camera_angle_limit_controller = camera_angle_limit_controller
        self._target_pan_angle = None
        self._target_tilt_angle = None
        self._target_zoom_index = None
        self._target_zoom_ratio = None
        self._current_pan_angle = None
        self._current_tilt_angle = None
        self._current_zoom_index = None
        self._current_zoom_ratio = None
        self._camera_speeds = CameraSpeeds()
        self._is_searching = False

        # TODO remove test targets below
        self._target_pan_angle = 10.0
        self._target_tilt_angle = 5.0
        # self._target_zoom_index = 10
        # self._target_zoom_ratio = 2.0

        # TODO add UI for target

    def start(self) -> None:
        assert not self._is_searching
        assert self._current_pan_angle is not None
        assert self._current_tilt_angle is not None
        self._is_searching = True
        if (self._target_pan_angle is not None
                and self._current_pan_angle is not None):
            delta_pan_angle_clockwise = get_delta_angle_clockwise(
                left=self._current_pan_angle, right=self._target_pan_angle)
            if delta_pan_angle_clockwise < 180:
                self._camera_speeds.pan_speed = self.pan_speed
                self._camera_angle_limit_controller.min_pan_angle = \
                    self._current_pan_angle
                self._camera_angle_limit_controller.max_pan_angle = \
                    self._target_pan_angle
            else:
                self._camera_speeds.pan_speed = -self.pan_speed
                self._camera_angle_limit_controller.min_pan_angle = \
                    self._target_pan_angle
                self._camera_angle_limit_controller.max_pan_angle = \
                    self._current_pan_angle
        if (self._target_tilt_angle is not None
                and self._current_tilt_angle is not None):
            delta_tilt_angle_clockwise = get_delta_angle_clockwise(
                left=self._current_tilt_angle, right=self._target_tilt_angle)
            if delta_tilt_angle_clockwise < 180:
                self._camera_speeds.tilt_speed = self.tilt_speed
                self._camera_angle_limit_controller.min_tilt_angle = \
                    self._current_tilt_angle
                self._camera_angle_limit_controller.max_tilt_angle = \
                    self._target_tilt_angle
            else:
                self._camera_speeds.tilt_speed = -self.tilt_speed
                self._camera_angle_limit_controller.min_tilt_angle = \
                    self._target_tilt_angle
                self._camera_angle_limit_controller.max_tilt_angle = \
                    self._current_tilt_angle
        if (self._target_zoom_ratio is not None
                and self._current_zoom_ratio is not None):
            assert isinstance(self._camera_zoom_limit_controller,
                              CameraZoomRatioLimitController)
            if self._current_zoom_ratio < self._target_zoom_ratio:
                self._camera_speeds.zoom_speed = ZoomSpeed.ZOOM_IN_SLOW
                self._camera_zoom_limit_controller.min_zoom_ratio = None
                self._camera_zoom_limit_controller.max_zoom_ratio = \
                    self._target_zoom_ratio
            elif self._current_zoom_ratio > self._target_zoom_ratio:
                self._camera_speeds.zoom_speed = ZoomSpeed.ZOOM_OUT_SLOW
                self._camera_zoom_limit_controller.min_zoom_ratio = \
                    self._target_zoom_ratio
                self._camera_zoom_limit_controller.max_zoom_ratio = None
            else:
                self._camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED
                self._camera_zoom_limit_controller.min_zoom_ratio = None
                self._camera_zoom_limit_controller.max_zoom_ratio = None
        if (self._target_zoom_index is not None
                and self._current_zoom_index is not None):
            assert isinstance(self._camera_zoom_limit_controller,
                              CameraZoomIndexLimitController)
            if self._current_zoom_index < self._target_zoom_index:
                self._camera_speeds.zoom_speed = ZoomSpeed.ZOOM_IN_SLOW
                self._camera_zoom_limit_controller.min_zoom_index = None
                self._camera_zoom_limit_controller.max_zoom_index = \
                    self._target_zoom_index
            elif self._current_zoom_index > self._target_zoom_index:
                self._camera_speeds.zoom_speed = ZoomSpeed.ZOOM_OUT_SLOW
                self._camera_zoom_limit_controller.min_zoom_index = \
                    self._target_zoom_index
                self._camera_zoom_limit_controller.max_zoom_index = None
            else:
                self._camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED
                self._camera_zoom_limit_controller.min_zoom_index = None
                self._camera_zoom_limit_controller.max_zoom_index = None

    def update_target(
            self,
            pan_angle: Optional[float],
            tilt_angle: Optional[float],
            zoom_index: Optional[int],
            zoom_ratio: Optional[float]):
        self._target_pan_angle = pan_angle
        self._target_tilt_angle = tilt_angle
        self._target_zoom_index = zoom_index
        self._target_zoom_ratio = zoom_ratio
        # TODO update camera speeds if called before start

    def update_current_angles(self, angles: Angles):
        self._current_pan_angle = angles.pan_angle
        self._current_tilt_angle = angles.tilt_angle
        # TODO calculate camera speeds if current angles are set the first time
        #   and target angles are already set

    def update_current_zoom_ratio(self, zoom_ratio: float):
        self._current_zoom_ratio = zoom_ratio
        # TODO calculate camera zoom speed if current zoom ratio is set the
        #   first time and target zoom speed is already set

    def update_current_zoom_index(self, zoom_index: int):
        self._current_zoom_index = zoom_index
        # TODO calculate camera zoom speed if current zoom index is set the
        #   first time and target zoom speed is already set

    def update(self, camera_speeds: CameraSpeeds) -> None:
        assert self._is_searching
        # The live view of the camera moves faster at higher zoom ratios.
        # Usually the pan and tilt speed should depend on the zoom ratio
        # (see https://github.com/maiermic/robot-cameraman/issues/13).
        # However, the camera should move in appropriate time
        # to the target position. With increasing target zoom,
        # the camera moves slower. If the pan/tilt distance is quite large,
        # the camera would take inappropriately long to pan/tilt to the target.
        # Hence, the camera should pan/tilt at maximum speed (as if zoom ratio
        # is 1.0) to the target. However, the speed is decreased near the
        # target to reach it more accurately. Angle deviations are reflected in
        # greater deviations in the live view with increasing zom ratio.
        #
        # Speed-Distance Diagram:
        #                     speed axis (ascending from bottom to top)
        #                          A
        #                          |
        #                max speed | ----\
        #              close speed |      \
        #           accurate speed |       \----|
        #                        0 |            \----
        #                          |
        #   distance axis (desc) --|--|--|||----|-------->
        #                             |  |||    0
        #    distance > max speed ----/  |||    |
        #    distance = max speed -------/||    |
        #    distance > accurate speed ---/|    |
        #    distance = accurate speed ----/    |
        #    distance = 0 ----------------------/
        zoom_ratio = self._current_zoom_ratio or 1.0

        pan_distance = get_angle_distance(left=self._target_pan_angle,
                                          right=self._current_pan_angle)
        if pan_distance < abs(self._camera_speeds.pan_speed):
            accurate_pan_speed = self._camera_speeds.pan_speed / zoom_ratio
            # use "accurate speed"
            camera_speeds.pan_speed = accurate_pan_speed
            # increase to "close speed"
            if pan_distance > abs(accurate_pan_speed):
                percentage = (
                        abs(pan_distance - abs(accurate_pan_speed))
                        / abs(self._camera_speeds.pan_speed
                              - accurate_pan_speed))
                camera_speeds.pan_speed += (
                        numpy.sign(self._camera_speeds.pan_speed)
                        * percentage
                        * abs(self._camera_speeds.pan_speed
                              - accurate_pan_speed))
        else:
            # use "max speed", since:  distance > max speed
            camera_speeds.pan_speed = self._camera_speeds.pan_speed

        tilt_distance = get_angle_distance(left=self._target_tilt_angle,
                                           right=self._current_tilt_angle)
        if tilt_distance < abs(self._camera_speeds.tilt_speed):
            accurate_tilt_speed = self._camera_speeds.tilt_speed / zoom_ratio
            # use "accurate speed"
            camera_speeds.tilt_speed = accurate_tilt_speed
            # increase to "close speed"
            if tilt_distance > abs(accurate_tilt_speed):
                percentage = (
                        abs(tilt_distance - abs(accurate_tilt_speed))
                        / abs(self._camera_speeds.tilt_speed
                              - accurate_tilt_speed))
                camera_speeds.tilt_speed += (
                        numpy.sign(self._camera_speeds.tilt_speed)
                        * percentage
                        * abs(self._camera_speeds.tilt_speed
                              - accurate_tilt_speed))
        else:
            # use "max speed", since:  distance > max speed
            camera_speeds.tilt_speed = self._camera_speeds.tilt_speed

        # TODO add option to zoom not until "close speed" (pan and tilt)
        #  is reached, since focus might be lost (=> blurry image),
        #  while camera pans/tilts (too) fast (for current zoom ratio).
        camera_speeds.zoom_speed = self._camera_speeds.zoom_speed
        self._camera_zoom_limit_controller.update(camera_speeds)
        self._camera_angle_limit_controller.update(camera_speeds)

    def stop(self):
        self._is_searching = False
        self._camera_speeds.reset()
