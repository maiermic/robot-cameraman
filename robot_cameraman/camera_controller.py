import logging
from abc import abstractmethod, ABC
from dataclasses import dataclass
from enum import Enum, auto
from logging import Logger
from math import isclose
from time import time
from typing import List, Optional

import numpy
import serial
from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from robot_cameraman.angle import get_delta_angle_clockwise, \
    get_delta_angle_counter_clockwise
from robot_cameraman.camera_speeds import ZoomSpeed, CameraSpeeds
from robot_cameraman.gimbal import Gimbal, Angles
from robot_cameraman.zoom import ZoomSteps, ZoomStep
from simplebgc.commands import GetAnglesInCmd
from simplebgc.gimbal import ControlMode
from simplebgc.units import to_degree, to_degree_per_sec

logger: Logger = logging.getLogger(__name__)


class CameraController(Protocol):
    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self, camera_speeds: CameraSpeeds) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_camera_moving(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def update(self, camera_speeds: CameraSpeeds) -> None:
        raise NotImplementedError


class SimpleCameraController(CameraController):
    yaw_speed: float = 0

    def __init__(self, gimbal: Gimbal) -> None:
        self.yaw_speed = 0
        self._gimbal = gimbal

    def start(self) -> None:
        return

    def stop(self, camera_speeds: CameraSpeeds) -> None:
        self.update(camera_speeds)

    def is_camera_moving(self) -> bool:
        return self.yaw_speed != 0

    def update(self, camera_speeds: CameraSpeeds) -> None:
        yaw_speed = camera_speeds.pan_speed
        if self.yaw_speed != yaw_speed:
            try:
                logger.debug('rotate gimbal with speed {}'.format(yaw_speed))
                self._gimbal.control(yaw_speed=yaw_speed)
                self.yaw_speed = yaw_speed
            except serial.serialutil.SerialException:
                logger.error('caught SerialException')


class ElapsedTime:
    _last_update_time: float

    def __init__(self):
        self._last_update_time: float = time()

    def reset(self):
        self._last_update_time = time()

    def update(self) -> float:
        current_time = time()
        elapsed_time = current_time - self._last_update_time
        self._last_update_time = current_time
        return elapsed_time

    def get(self) -> float:
        return time() - self._last_update_time


class SpeedManager:
    def __init__(self, acceleration_per_second: float = 400,
                 elapsed_time: ElapsedTime = None):
        if elapsed_time is None:
            elapsed_time = ElapsedTime()
        self._elapsed_time = elapsed_time
        self.acceleration_per_second: float = acceleration_per_second
        self.target_speed: float = 0
        self.current_speed: float = 0

    def reset(self):
        self._elapsed_time.reset()

    def is_target_speed_reached(self):
        return self.current_speed == self.target_speed

    def update(self) -> float:
        elapsed_time = self._elapsed_time.update()
        delta_speed = self.target_speed - self.current_speed
        acceleration = min(self.acceleration_per_second * elapsed_time,
                           abs(delta_speed))
        self.current_speed += numpy.sign(delta_speed) * acceleration
        return self.current_speed


class SmoothCameraController(CameraController):
    _rotate_speed_manager: SpeedManager
    _tilt_speed_manager: SpeedManager
    _old_zoom_speed: ZoomSpeed = ZoomSpeed.ZOOM_STOPPED

    def __init__(self,
                 gimbal: Gimbal,
                 camera_manager: PanasonicCameraManager,
                 rotate_speed_manager: SpeedManager,
                 tilt_speed_manager: SpeedManager):
        self._gimbal = gimbal
        self._camera_manager = camera_manager
        self._rotate_speed_manager = rotate_speed_manager
        self._tilt_speed_manager = tilt_speed_manager

    def start(self) -> None:
        self._rotate_speed_manager.reset()
        self._tilt_speed_manager.reset()

    def update(self, camera_speeds: CameraSpeeds) -> None:
        logger.debug('new speeds: pan %5d, tilt %5d',
                     camera_speeds.pan_speed,
                     camera_speeds.tilt_speed)
        self._rotate_speed_manager.target_speed = camera_speeds.pan_speed
        self._tilt_speed_manager.target_speed = camera_speeds.tilt_speed
        old_speed = self._rotate_speed_manager.current_speed
        old_tilt_speed = self._tilt_speed_manager.current_speed
        try:
            logger.debug('current gimbal accelerations are: pan %5d, tilt %5d',
                         self._rotate_speed_manager.acceleration_per_second,
                         self._tilt_speed_manager.acceleration_per_second)
            self._gimbal.control(yaw_speed=self._rotate_speed_manager.update(),
                                 pitch_speed=self._tilt_speed_manager.update())
            logger.debug('current gimbal speeds are: pan %5d, tilt %5d',
                         self._rotate_speed_manager.current_speed,
                         self._tilt_speed_manager.current_speed)
        except serial.serialutil.SerialException as e:
            logger.error(f'failed to control gimbal: {e}')
            self._rotate_speed_manager.current_speed = old_speed
            self._tilt_speed_manager.current_speed = old_tilt_speed
        try:
            camera = self._camera_manager.camera
            if camera is not None:
                logger.debug('zoom: new {: >5}, old {: >5}'.format(
                    camera_speeds.zoom_speed, self._old_zoom_speed))
                if camera_speeds.zoom_speed is not self._old_zoom_speed:
                    if camera_speeds.zoom_speed is ZoomSpeed.ZOOM_IN_FAST:
                        logger.debug('zoom in fast')
                        camera.zoom_in_fast()
                    elif camera_speeds.zoom_speed is ZoomSpeed.ZOOM_IN_SLOW:
                        logger.debug('zoom in slow')
                        camera.zoom_in_fast()
                    elif camera_speeds.zoom_speed is ZoomSpeed.ZOOM_STOPPED:
                        logger.debug('zoom stop')
                        camera.zoom_stop()
                    elif camera_speeds.zoom_speed is ZoomSpeed.ZOOM_OUT_SLOW:
                        logger.debug('zoom out slow')
                        camera.zoom_out_slow()
                    elif camera_speeds.zoom_speed is ZoomSpeed.ZOOM_OUT_FAST:
                        logger.debug('zoom out fast')
                        camera.zoom_out_fast()
                self._old_zoom_speed = camera_speeds.zoom_speed
        except Exception as e:
            logger.error('failed to zoom camera: %s', e)

    def is_camera_moving(self) -> bool:
        return (self._rotate_speed_manager.current_speed != 0
                or self._tilt_speed_manager.current_speed != 0)

    def stop(self, camera_speeds: CameraSpeeds) -> None:
        while self.is_camera_moving():
            self.update(camera_speeds)


class CameraZoomLimitController(Protocol):
    @abstractmethod
    def update(self, camera_speeds: CameraSpeeds) -> None:
        raise NotImplementedError


class CameraZoomRatioLimitController(CameraZoomLimitController):
    zoom_ratio: Optional[float]
    min_zoom_ratio: Optional[float]
    max_zoom_ratio: Optional[float]

    def __init__(self) -> None:
        self.zoom_ratio = None
        self.min_zoom_ratio = None
        self.max_zoom_ratio = None

    def update_zoom_ratio(self, zoom_ratio: float):
        self.zoom_ratio = zoom_ratio

    def update(self, camera_speeds: CameraSpeeds) -> None:
        if self.zoom_ratio is None:
            return
        logger.debug(
            f'check if current zoom ratio {self.zoom_ratio} reached limit')
        if (self._is_heading_towards_min(camera_speeds.zoom_speed)
                and self.is_min_reached()):
            logger.debug('min zoom ratio reached, zoom speed is set to 0')
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED
        if (self._is_heading_towards_max(camera_speeds.zoom_speed)
                and self.is_max_reached()):
            logger.debug('max zoom ratio reached, zoom speed is set to 0')
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED

    def _is_heading_towards_min(self, zoom_speed: ZoomSpeed):
        return self.min_zoom_ratio is not None and zoom_speed < 0

    def is_min_reached(self):
        return self.zoom_ratio <= self.min_zoom_ratio

    def _is_heading_towards_max(self, zoom_speed: ZoomSpeed):
        return self.max_zoom_ratio is not None and zoom_speed > 0

    def is_max_reached(self):
        return self.zoom_ratio >= self.max_zoom_ratio


class PredictiveCameraZoomRatioLimitController(CameraZoomRatioLimitController):
    _zoom_steps: ZoomSteps
    _previous_zoom_speed: Optional[ZoomSpeed]
    _previous_zoom_ratio: Optional[float]
    _current_zoom_step: Optional[ZoomStep]
    _time_since_zoom_ratio_reached: ElapsedTime
    _time_since_last_update: Optional[ElapsedTime]

    def __init__(self, zoom_steps: ZoomSteps) -> None:
        super().__init__()
        self._zoom_steps = zoom_steps
        self._previous_zoom_speed = None
        self._previous_zoom_ratio = None
        self._current_zoom_step = None
        self._time_since_zoom_ratio_reached = ElapsedTime()
        self._time_since_last_update = None

    def update_zoom_ratio(self, zoom_ratio: float):
        self._previous_zoom_ratio = self.zoom_ratio
        super().update_zoom_ratio(zoom_ratio)
        if (self._previous_zoom_ratio is None
                or self._previous_zoom_ratio != self.zoom_ratio):
            self._time_since_zoom_ratio_reached.reset()
            self._current_zoom_step = \
                self._zoom_steps.get_by_zoom_ratio(self.zoom_ratio)

    def _update_time_since_last_update(self) -> Optional[float]:
        if self._time_since_last_update is None:
            self._time_since_last_update = ElapsedTime()
            return None
        return self._time_since_last_update.update()

    def update(self, camera_speeds: CameraSpeeds) -> None:
        time_since_last_update = self._update_time_since_last_update()
        super().update(camera_speeds)
        # TODO predict zoom out similar to zoom in
        # if self._is_heading_towards_min(camera_speeds.zoom_speed):
        #     logger.debug('min zoom ratio reached, zoom speed is set to 0')
        #     camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED
        if self._is_heading_towards_max(camera_speeds.zoom_speed):
            next_zoom_step = \
                self._zoom_steps.get_next_greater(self._current_zoom_step)
            t = self._time_since_zoom_ratio_reached.get()
            t_up = time_since_last_update or 0
            # TODO the magic number 0.25 led to better results in experiments
            #   with a Panasonic DMC-LF1, but this value/delay might not work
            #   as well with all cameras (different FPS) or configurations
            #   (object tracking vs. color tracking)
            time_to_stop = t + t_up + 0.25
            logger.debug(
                f'heading towards max zoom ratio {self.max_zoom_ratio},'
                f' time since last update={time_since_last_update},'
                f' current={self.zoom_ratio},'
                f' time since current has been reached={t},'
                f' next={next_zoom_step.zoom_ratio},'
                f' min stop time={next_zoom_step.min_stop_zoom_in_time},'
                f' time to stop={time_to_stop}')
            if (next_zoom_step.zoom_ratio == self.max_zoom_ratio
                    and next_zoom_step.min_stop_zoom_in_time <= time_to_stop):
                logger.debug('max zoom ratio is predicted to be reached soon,'
                             ' zoom speed is set to 0')
                camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED
        if camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED:
            self._time_since_zoom_ratio_reached.reset()
        self._previous_zoom_speed = camera_speeds.zoom_speed


class CameraZoomIndexLimitController(CameraZoomLimitController):
    zoom_index: Optional[int]
    min_zoom_index: Optional[int]
    max_zoom_index: Optional[int]

    def __init__(self) -> None:
        self.zoom_index = None
        self.min_zoom_index = None
        self.max_zoom_index = None

    def update_zoom_index(self, zoom_index: int):
        self.zoom_index = zoom_index

    def update(self, camera_speeds: CameraSpeeds) -> None:
        if self.zoom_index is None:
            return
        logger.debug(
            f'check if current zoom index {self.zoom_index} reached limit')
        if (self._is_heading_towards_min(camera_speeds.zoom_speed)
                and self.is_min_reached()):
            logger.debug('min zoom index reached, zoom speed is set to 0')
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED
        if (self._is_heading_towards_max(camera_speeds.zoom_speed)
                and self.is_max_reached()):
            logger.debug('max zoom index reached, zoom speed is set to 0')
            camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED

    def _is_heading_towards_min(self, zoom_speed: ZoomSpeed):
        return self.min_zoom_index is not None and zoom_speed < 0

    def is_min_reached(self):
        return self.zoom_index <= self.min_zoom_index

    def _is_heading_towards_max(self, zoom_speed: ZoomSpeed):
        return self.max_zoom_index is not None and zoom_speed > 0

    def is_max_reached(self):
        return self.zoom_index >= self.max_zoom_index


class CameraAngleLimitController:
    min_pan_angle: Optional[float]
    max_pan_angle: Optional[float]
    min_tilt_angle: Optional[float]
    max_tilt_angle: Optional[float]
    _current_pan_angle: Optional[float]
    _current_tilt_angle: Optional[float]

    def __init__(self) -> None:
        super().__init__()
        self.min_pan_angle = None
        self.max_pan_angle = None
        self.min_tilt_angle = None
        self.max_tilt_angle = None
        self._current_pan_angle = None
        self._current_tilt_angle = None

    def update_current_angles(self, angles: Angles):
        self._current_pan_angle = angles.pan_angle
        self._current_tilt_angle = angles.tilt_angle

    def update(self, camera_speeds: CameraSpeeds) -> None:
        if (self._current_pan_angle is None
                or self._current_tilt_angle is None):
            logger.debug('current angles are not set yet')
            return
        logger.debug(', '.join((
            f"pan angle: {self._current_pan_angle:4.1f}",
            f"tilt angle: {self._current_tilt_angle:4.1f}",
        )))

        # Since camera might rotate full circle, a single limit could be
        # reached rotating clockwise or counter clockwise. It is unrealistic
        # that the exact limit is reached and kept. Thereby, the camera might
        # pass over the limit. If there is only one limit,
        # the camera may continue to move after it passed the limit,
        # since the limit is in the opposite rotating direction than the camera
        # is moving.
        #
        # Minimum and maximum have to be defined both.
        # They define a range, in which the camera stops,
        # i.e. the camera stops after a limit is passed.
        # The camera may only move to the closer limit to exit this range.
        if (self.min_pan_angle is not None
                and self.max_pan_angle is not None
                and is_angle_between(
                    left=self.min_pan_angle,
                    angle=self._current_pan_angle,
                    right=self.max_pan_angle,
                    clockwise=False)):
            min_pan_delta = get_delta_angle_clockwise(
                left=self._current_pan_angle, right=self.min_pan_angle)
            max_pan_delta = get_delta_angle_counter_clockwise(
                left=self._current_pan_angle, right=self.max_pan_angle)
            if min_pan_delta < max_pan_delta:
                if camera_speeds.pan_speed < 0:
                    logger.debug(
                        'min pan angle reached, pan speed is set to 0')
                    camera_speeds.pan_speed = 0
            else:
                if camera_speeds.pan_speed > 0:
                    logger.debug(
                        'max pan angle reached, pan speed is set to 0')
                    camera_speeds.pan_speed = 0

        if (self.min_tilt_angle is not None
                and self.max_tilt_angle is not None
                and is_angle_between(
                    left=self.min_tilt_angle,
                    angle=self._current_tilt_angle,
                    right=self.max_tilt_angle,
                    clockwise=False)):
            min_tilt_delta = get_delta_angle_clockwise(
                left=self._current_tilt_angle, right=self.min_tilt_angle)
            max_tilt_delta = get_delta_angle_counter_clockwise(
                left=self._current_tilt_angle, right=self.max_tilt_angle)
            if min_tilt_delta < max_tilt_delta:
                if camera_speeds.tilt_speed < 0:
                    logger.debug(
                        'min tilt angle reached, tilt speed is set to 0')
                    camera_speeds.tilt_speed = 0
            else:
                if camera_speeds.tilt_speed > 0:
                    logger.debug(
                        'max tilt angle reached, tilt speed is set to 0')
                    camera_speeds.tilt_speed = 0


@dataclass()
class PointOfMotion:
    pan_angle: float = 0
    pan_clockwise: bool = True
    tilt_angle: float = 0
    tilt_clockwise: bool = True
    time: float = 0.0
    zoom_factor: float = 1.0


# TODO pass to controllers instead of CameraSpeeds only
@dataclass()
class CameraState:
    speeds: CameraSpeeds
    pan_angle: float
    tilt_angle: float
    zoom_factor: float = 1.0


class PointOfMotionTargetSpeedCalculator:
    def __init__(self, max_pan_speed: float = 60, max_tilt_speed: float = 12):
        self._max_pan_speed = max_pan_speed
        self._max_tilt_speed = max_tilt_speed

    # TODO does not need the whole state only angles
    def calculate(self, state: CameraState, target: PointOfMotion):
        if target.time == 0:
            return CameraSpeeds(pan_speed=self._max_pan_speed,
                                tilt_speed=self._max_tilt_speed)
        return CameraSpeeds(
            pan_speed=min(self._max_pan_speed,
                          self.get_degree_per_second(state.pan_angle,
                                                     target.pan_angle,
                                                     target.pan_clockwise,
                                                     target.time)),
            tilt_speed=min(self._max_tilt_speed,
                           self.get_degree_per_second(state.tilt_angle,
                                                      target.tilt_angle,
                                                      target.tilt_clockwise,
                                                      target.time)))

    @classmethod
    def get_degree_per_second(
            cls,
            current_angle: float,
            target_angle: float,
            clockwise: bool,
            travel_time: float) -> float:
        if clockwise:
            delta_angle = get_delta_angle_clockwise(
                left=current_angle, right=target_angle)
        else:
            delta_angle = get_delta_angle_counter_clockwise(
                left=current_angle, right=target_angle)
        return delta_angle / travel_time


class PathOfMotionCameraController(ABC):
    def __init__(self):
        self._path: List[PointOfMotion] = []
        self._current_point_index = 0

    def has_points(self):
        return bool(self._path)

    def add_point(self, point: PointOfMotion) -> None:
        self._path.append(point)

    def current_point(self):
        return self._path[self._current_point_index]

    def get_next_point(self):
        return self._path[self._current_point_index + 1]

    def has_next_point(self):
        return (self._current_point_index + 1) < len(self._path)

    def next_point(self):
        self._current_point_index = min(self._current_point_index + 1,
                                        len(self._path))

    def is_end_of_path_reached(self):
        return self._current_point_index >= len(self._path)

    @abstractmethod
    def update(self, camera_speeds: CameraSpeeds) -> None:
        raise NotImplementedError


# TODO consider time to accelerate and decelerate,
#   e.g. it takes currently 6.5s instead of 6s if camera needs to accelerate
#   and decelerate (i.e. camera moves slower than calculated target speed in
#   that time)
#   e.g. accelerate and decelerate (according to next point) before
#   intermediate point without stop is reached
# TODO easier definition of full rotations
# TODO wait if same point as before is given, but with a time > 0
# TODO zoom
# TODO move more than 360° (e.g. 0 -> 180 -> 360)
class BaseCamPathOfMotionCameraController(PathOfMotionCameraController):
    class _State(Enum):
        """The controller has to be started using """
        STARTED = auto()
        RUNNING = auto()
        STOPPED = auto()

    def __init__(self,
                 gimbal: Gimbal,
                 rotate_speed_manager: SpeedManager,
                 tilt_speed_manager: SpeedManager,
                 target_speed_calculator: PointOfMotionTargetSpeedCalculator):
        super().__init__()
        self._gimbal = gimbal
        self._is_end_of_path_reached = False
        self._rotate_speed_manager = rotate_speed_manager
        self._tilt_speed_manager = tilt_speed_manager
        self._target_speed_calculator = target_speed_calculator
        self._state = self._State.STOPPED
        self._previous_point: Optional[PointOfMotion] = None

    def next_point(self):
        self._previous_point = self.current_point()
        super().next_point()

    def start(self):
        self._reset_speed_managers()
        self._state = self._State.STARTED

    def update(self, camera_speeds: CameraSpeeds) -> None:
        assert self._state is not self._State.STOPPED
        if not self.has_points():
            return
        angles = self._gimbal.get_angles()
        _log_angles(angles)
        camera_speeds.pan_speed = to_degree_per_sec(angles.target_speed_3)
        camera_speeds.tilt_speed = to_degree_per_sec(angles.target_speed_2)
        if self._state is self._State.STARTED:
            self._state = self._State.RUNNING
            if self._is_current_point_reached(angles):
                if self.has_next_point():
                    self.next_point()
                else:
                    self._stop()
                    return
            else:
                pan_angle = to_degree(angles.target_angle_3)
                tilt_angle = to_degree(angles.target_angle_2)
                self._previous_point = PointOfMotion(pan_angle=pan_angle,
                                                     tilt_angle=tilt_angle)
            assert self._previous_point is not None
            self._update_target_speeds(camera_speeds, self._previous_point)
            self._update_speed_managers()
            self._move_gimbal_to_current_point()
        elif self._is_current_point_reached(angles):
            logger.debug('move to next point')
            if self.has_next_point():
                self.next_point()
                current_point = self.current_point()
                previous = self._previous_point
                # If the gimbal switches moving direction (clockwise <-> counter
                # clockwise), then it stopped by itself, when it reached the
                # last point. The speed managers don't know that. Hence, the
                # current speed has to be set to zero and then updated.
                if previous.pan_clockwise != current_point.pan_clockwise:
                    logger.debug('reset pan speed to 0')
                    self._rotate_speed_manager.current_speed = 0
                if previous.tilt_clockwise != current_point.tilt_clockwise:
                    logger.debug('reset tilt speed to 0')
                    self._tilt_speed_manager.current_speed = 0
                # TODO consider to update target speeds based on real angles
                #   of gimbal, since they may be different than the target
                #   point, which is assumed has been reached exactly.
                #   However, overstepping has to be considered.
                # pan_angle = to_degree(angles.target_angle_3)
                # tilt_angle = to_degree(angles.target_angle_2)
                # real_current_point = PointOfMotion(pan_angle=pan_angle,
                #                                    tilt_angle=tilt_angle)
                # self._update_target_speeds(camera_speeds, real_current_point)
                # TODO only pass angles instead of PointOfMotion
                self._update_target_speeds(camera_speeds, previous)
                self._update_speed_managers()
                self._move_gimbal_to_current_point()
            else:
                self._stop()
        elif not self.is_target_speed_reached():
            logger.debug('increase speed')
            self._update_speed_managers()
            self._move_gimbal_to_current_point()
        else:
            logger.debug('reached target speed')
            # update elapsed time of speed managers
            self._update_speed_managers()

    def _stop(self):
        # indicates that end of path is reached
        self.next_point()
        self._state = self._State.STOPPED

    def _reset_speed_managers(self):
        self._rotate_speed_manager.reset()
        self._tilt_speed_manager.reset()

    def _update_speed_managers(self):
        self._rotate_speed_manager.update()
        self._tilt_speed_manager.update()

    def _update_target_speeds(self, camera_speeds: CameraSpeeds,
                              previous_point: PointOfMotion):
        next_point = self.current_point()
        camera_state = CameraState(speeds=camera_speeds,
                                   pan_angle=previous_point.pan_angle,
                                   tilt_angle=previous_point.tilt_angle)
        logger.debug(f'camera state {camera_state}')
        logger.debug(f'next point {next_point}')
        next_but_one_point = \
            self.get_next_point() if self.has_next_point() else None
        logger.debug(f'next but one point {next_but_one_point}')
        target_speeds = self._target_speed_calculator.calculate(
            camera_state, next_point)
        logger.debug(f'target speeds {target_speeds}')
        self._rotate_speed_manager.target_speed = target_speeds.pan_speed
        self._tilt_speed_manager.target_speed = target_speeds.tilt_speed

    def is_target_speed_reached(self):
        return (self._rotate_speed_manager.is_target_speed_reached()
                and self._tilt_speed_manager.is_target_speed_reached())

    def _is_current_point_reached(self, angles: GetAnglesInCmd):
        next_point = self.get_next_point() if self.has_next_point() else None
        return is_current_point_reached(
            pan_angle=to_degree(angles.target_angle_3),
            tilt_angle=to_degree(angles.target_angle_2),
            current_target=self.current_point(),
            next_target=next_point)

    @classmethod
    def _current_speed(cls, speed_manager: SpeedManager):
        # TODO this detail is specific to SimpleBGC gimbals.
        #   The logic should be moved as the controller should be independent
        #   of the used gimbal.
        # Never return 0, since then the value is omitted (see page 34 of
        # SimpleBGC 2.6 serial protocol specification)
        return max(1.0, speed_manager.current_speed)

    def _move_gimbal_to_current_point(self):
        if not self.is_end_of_path_reached():
            current_point = self.current_point()
            pan_angle = current_point.pan_angle
            tilt_angle = current_point.tilt_angle
            if self.has_next_point():
                next_point = self.get_next_point()
                # Do not stop at intermediate/current point if the next point
                # is in the same direction.
                if current_point.pan_clockwise == next_point.pan_clockwise:
                    pan_angle = next_point.pan_angle
                if current_point.tilt_clockwise == next_point.tilt_clockwise:
                    tilt_angle = next_point.tilt_angle
            yaw_speed = self._current_speed(self._rotate_speed_manager)
            pitch_speed = self._current_speed(self._tilt_speed_manager)
            logger.debug(' '.join((
                f'pan to {pan_angle}',
                f'with {self._rotate_speed_manager.current_speed}°/s,',
                f'tilt to {tilt_angle}',
                f'with {self._tilt_speed_manager.current_speed}°/s',
            )))
            self._gimbal.control(
                yaw_mode=ControlMode.angle, yaw_speed=yaw_speed,
                yaw_angle=pan_angle,
                pitch_mode=ControlMode.angle, pitch_speed=pitch_speed,
                pitch_angle=tilt_angle)


def _log_angles(angles: GetAnglesInCmd):
    logger.debug(' '.join((
        'pan:',
        f'{to_degree(angles.target_angle_3):6.2f}°',
        f'{to_degree_per_sec(angles.target_speed_3):6.2f}°/s',
        ' ' * 4,
        'tilt:',
        f'{to_degree(angles.target_angle_2):6.2f}°',
        f'{to_degree_per_sec(angles.target_speed_2):6.2f}°/s',
    )))


def is_current_point_reached(
        pan_angle: float,
        tilt_angle: float,
        current_target: PointOfMotion,
        next_target: Optional[PointOfMotion]) -> bool:
    next_pan_angle = getattr(next_target, 'pan_angle', None)
    next_pan_clockwise = getattr(next_target, 'pan_clockwise', None)
    next_tilt_angle = getattr(next_target, 'tilt_angle', None)
    next_tilt_clockwise = getattr(next_target, 'tilt_clockwise', None)
    pan_reached = is_current_angle_reached(
        current_angle=pan_angle,
        current_target_angle=current_target.pan_angle,
        current_target_rotate_clockwise=current_target.pan_clockwise,
        next_target_angle=next_pan_angle,
        next_target_rotate_clockwise=next_pan_clockwise)
    tilt_reached = is_current_angle_reached(
        current_angle=tilt_angle,
        current_target_angle=current_target.tilt_angle,
        current_target_rotate_clockwise=current_target.tilt_clockwise,
        next_target_angle=next_tilt_angle,
        next_target_rotate_clockwise=next_tilt_clockwise)
    if pan_reached:
        logger.debug(f'pan angle reached {current_target.pan_angle:.2f}°')
    if tilt_reached:
        logger.debug(f'tilt angle reached {current_target.tilt_angle:.2f}°')
    return pan_reached and tilt_reached


def is_current_angle_reached(
        current_angle: float,
        current_target_angle: float,
        current_target_rotate_clockwise: bool,
        next_target_angle: float,
        next_target_rotate_clockwise: bool) -> bool:
    if is_close_angle(current_target_angle, current_angle, abs_tol=0.05):
        return True
    if current_target_rotate_clockwise == next_target_rotate_clockwise:
        return is_angle_between(
            left=current_target_angle,
            angle=current_angle,
            right=next_target_angle,
            clockwise=current_target_rotate_clockwise)
    return False


def is_close_angle(a: float, b: float, abs_tol: float) -> bool:
    """
    Determine whether the two angles are close in value.

      abs_tol
        maximum difference for being considered "close", regardless of the
        magnitude of the input values
    """
    if isclose(a, b, abs_tol=abs_tol):
        return True
    a_distance_to_overstep = abs(360 - a) % 360
    b_distance_to_overstep = abs(360 - b) % 360
    return a_distance_to_overstep + b_distance_to_overstep <= abs_tol


def is_angle_between(
        left: float, angle: float, right: float, clockwise: bool) -> bool:
    if clockwise:
        if left <= right:
            return left <= angle <= right
        else:
            return left <= angle or angle <= right
    else:
        if left >= right:
            return left >= angle >= right
        else:
            return left >= angle or angle >= right


def _main():
    from time import sleep
    from robot_cameraman.gimbal import create_simple_bgc_gimbal
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(name)-50s %(levelname)-8s %(message)s')
    controller = BaseCamPathOfMotionCameraController(
        create_simple_bgc_gimbal(),
        rotate_speed_manager=SpeedManager(60),
        tilt_speed_manager=SpeedManager(12),
        target_speed_calculator=PointOfMotionTargetSpeedCalculator())
    controller.add_point(PointOfMotion(pan_angle=0, pan_clockwise=False,
                                       tilt_angle=0, tilt_clockwise=False))
    controller.add_point(PointOfMotion(pan_angle=180, pan_clockwise=True,
                                       tilt_angle=30, tilt_clockwise=True,
                                       time=6))
    controller.add_point(PointOfMotion(pan_angle=270, pan_clockwise=True,
                                       tilt_angle=15, tilt_clockwise=False,
                                       time=3))
    controller.add_point(PointOfMotion(pan_angle=0, pan_clockwise=False,
                                       tilt_angle=0, tilt_clockwise=False,
                                       time=3))
    camera_speeds = CameraSpeeds()
    controller.start()
    while not controller.is_end_of_path_reached():
        sleep(1 / 15)
        controller.update(camera_speeds)


if __name__ == '__main__':
    _main()
