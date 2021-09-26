import logging
from abc import abstractmethod, ABC
from dataclasses import dataclass
from enum import Enum, auto
from logging import Logger
from typing import List, Optional

import numpy
import serial
from math import isclose
from more_itertools import grouper
from time import time
from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from robot_cameraman.tracking import CameraSpeeds
from simplebgc.commands import GetAnglesInCmd
from simplebgc.gimbal import Gimbal, ControlMode
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
    yaw_speed: int = 0

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


class SpeedManager:
    def __init__(self, acceleration_per_second: int = 400,
                 elapsed_time: ElapsedTime = None):
        if elapsed_time is None:
            elapsed_time = ElapsedTime()
        self._elapsed_time = elapsed_time
        self.acceleration_per_second: int = acceleration_per_second
        self.target_speed: int = 0
        self.current_speed: int = 0

    def reset(self):
        self._elapsed_time.reset()

    def is_target_speed_reached(self):
        return self.current_speed == self.target_speed

    def update(self) -> int:
        elapsed_time = self._elapsed_time.update()
        delta_speed = self.target_speed - self.current_speed
        acceleration = min(self.acceleration_per_second * elapsed_time,
                           abs(delta_speed))
        self.current_speed += int(round(numpy.sign(delta_speed) * acceleration))
        return self.current_speed


class SmoothCameraController(CameraController):
    _rotate_speed_manager: SpeedManager
    _tilt_speed_manager: SpeedManager
    _old_zoom_speed: int = 0

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
            self._gimbal.control(yaw_speed=self._rotate_speed_manager.update(),
                                 pitch_speed=-self._tilt_speed_manager.update())
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
                if camera_speeds.zoom_speed > 0 >= self._old_zoom_speed:
                    logger.debug('zoom in')
                    camera.zoom_in_fast()
                elif camera_speeds.zoom_speed < 0 <= self._old_zoom_speed:
                    logger.debug('zoom out')
                    camera.zoom_out_fast()
                elif camera_speeds.zoom_speed == 0 != self._old_zoom_speed:
                    logger.debug('zoom stop')
                    camera.zoom_stop()
                self._old_zoom_speed = camera_speeds.zoom_speed
        except Exception as e:
            logger.error('failed to zoom camera: %s', e)

    def is_camera_moving(self) -> bool:
        return (self._rotate_speed_manager.current_speed != 0
                or self._tilt_speed_manager.current_speed != 0)

    def stop(self, camera_speeds: CameraSpeeds) -> None:
        while self.is_camera_moving():
            self.update(camera_speeds)


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
    def __init__(self, max_pan_speed: int = 60, max_tilt_speed: int = 12):
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
            time: float) -> float:
        if clockwise:
            delta_angle = cls.get_delta_angle_clockwise(
                current_angle=current_angle, target_angle=target_angle)
        else:
            delta_angle = cls.get_delta_angle_counter_clockwise(
                current_angle=current_angle, target_angle=target_angle)
        return delta_angle / time

    @classmethod
    def get_delta_angle_clockwise(
            cls, current_angle: float, target_angle: float) -> float:
        return abs(360 - current_angle) % 360 + target_angle

    @classmethod
    def get_delta_angle_counter_clockwise(
            cls, current_angle: float, target_angle: float) -> float:
        if current_angle >= target_angle:
            return current_angle - target_angle
        else:
            return abs(360 - target_angle) + current_angle


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
                current_point = self.current_point()
                # should have been set when started (first call of update)
                assert self._previous_point is not None
                previous = self._previous_point
                # If the gimbal switches moving direction (clockwise <-> counter
                # clockwise), then it stopped by itself, when it reached the
                # last point. The speed managers don't know that. Hence, the
                # current speed has to be set to zero and then updated.
                if previous.pan_clockwise != current_point.pan_clockwise:
                    self._rotate_speed_manager.current_speed = 0
                if previous.tilt_clockwise != current_point.tilt_clockwise:
                    self._tilt_speed_manager.current_speed = 0
                self.next_point()
                self._update_target_speeds(camera_speeds, current_point)
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
        target_speeds = self._target_speed_calculator.calculate(
            camera_state, next_point)
        self._rotate_speed_manager.target_speed = target_speeds.pan_speed
        self._tilt_speed_manager.target_speed = target_speeds.tilt_speed

    def is_target_speed_reached(self):
        return (self._rotate_speed_manager.is_target_speed_reached()
                and self._tilt_speed_manager.is_target_speed_reached())

    def _is_current_point_reached(self, angles: GetAnglesInCmd):
        pan_angle = to_degree(angles.target_angle_3)
        tilt_angle = to_degree(angles.target_angle_2)
        p = self.current_point()
        return (isclose(p.pan_angle, pan_angle, abs_tol=0.05)
                and isclose(p.tilt_angle, tilt_angle, abs_tol=0.05))

    @classmethod
    def _current_speed(cls, speed_manager: SpeedManager):
        # Never return 0, since then the value is omitted (see page 34 of
        # SimpleBGC 2.6 serial protocol specification)
        return max(1, speed_manager.current_speed)

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
            self._gimbal.control(
                yaw_mode=ControlMode.angle, yaw_speed=yaw_speed,
                yaw_angle=pan_angle,
                pitch_mode=ControlMode.angle, pitch_speed=pitch_speed,
                pitch_angle=tilt_angle)


def _log_angles(angles: GetAnglesInCmd):
    column_names = ('imu_angle', 'target_angle', 'target_speed')
    logger.debug('\t'.join(column_names))
    # noinspection Mypy
    for imu_angle, target_angle, target_speed in grouper(angles, 3):
        logger.debug('\t'.join((
            f'{to_degree(imu_angle):{len(column_names[0]) - 1}.2f}°',
            f'{to_degree(target_angle):{len(column_names[1]) - 1}.2f}°',
            f'{to_degree_per_sec(target_speed):{len(column_names[2]) - 3}.2f}°/s')))


def _main():
    from time import sleep
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(name)-50s %(levelname)-8s %(message)s')
    controller = BaseCamPathOfMotionCameraController(
        Gimbal(),
        rotate_speed_manager=SpeedManager(60),
        tilt_speed_manager=SpeedManager(12),
        target_speed_calculator=PointOfMotionTargetSpeedCalculator())
    controller.add_point(PointOfMotion(pan_angle=0, pan_clockwise=False,
                                       tilt_angle=0, tilt_clockwise=False))
    controller.add_point(PointOfMotion(pan_angle=180, pan_clockwise=True,
                                       tilt_angle=30, tilt_clockwise=True,
                                       time=6))
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
