import logging
from abc import abstractmethod, ABC
from dataclasses import dataclass
from logging import Logger
from typing import List

import numpy
import serial
from more_itertools import grouper
from time import time
from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from robot_cameraman.tracking import CameraSpeeds
from simplebgc.commands import GetAnglesInCmd
from simplebgc.serial_example import control_gimbal, rotate_gimbal, \
    degree_factor, degree_per_sec_factor, get_angles

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
                rotate_gimbal(yaw_speed)
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
    def __init__(self, acceleration_per_second: int = 400):
        self._elapsed_time: ElapsedTime = ElapsedTime()
        self.acceleration_per_second: int = acceleration_per_second
        self.target_speed: int = 0
        self.current_speed: int = 0

    def reset(self):
        self._elapsed_time.reset()

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
                 camera_manager: PanasonicCameraManager,
                 rotate_speed_manager: SpeedManager,
                 tilt_speed_manager: SpeedManager):
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
            control_gimbal(yaw_speed=self._rotate_speed_manager.update(),
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
    pan_angle: int = 0
    pan_clockwise: bool = True
    tilt_angle: int = 0
    tilt_clockwise: bool = True
    zoom_factor: float = 1.0


# TODO pass to controllers instead of CameraSpeeds only
@dataclass()
class CameraState:
    speeds: CameraSpeeds
    pan_angle: int
    tilt_angle: int
    zoom_factor: float = 1.0


class PathOfMotionCameraController(ABC):
    def __init__(self):
        self._path: List[PointOfMotion] = []
        self._next_point_index = 0

    def add_point(self, point: PointOfMotion) -> None:
        self._path.append(point)

    def current_point(self):
        return self._path[self._next_point_index]

    def next_point(self):
        self._next_point_index = min(self._next_point_index + 1,
                                     len(self._path))

    def is_end_of_path_reached(self):
        return self._next_point_index >= len(self._path)

    @abstractmethod
    def update(self, camera_speeds: CameraSpeeds) -> None:
        raise NotImplementedError


class BaseCamPathOfMotionCameraController(PathOfMotionCameraController):

    def __init__(self, connection: serial.Serial):
        super().__init__()
        self._connection = connection
        self._is_end_of_path_reached = False

    def update(self, camera_speeds: CameraSpeeds) -> None:
        # TODO use SpeedManager to start movement gradually
        if self._is_current_point_reached():
            self.next_point()
            self._move_gimbal_to_current_point()

    def start(self):
        self._move_gimbal_to_current_point()

    def _is_current_point_reached(self):
        angles = get_angles(self._connection)
        _print_angles(angles)
        pan_angle = angles.target_angle_3 * degree_factor
        pan_speed = angles.target_speed_3 * degree_per_sec_factor
        tilt_angle = angles.target_angle_2 * degree_factor
        tilt_speed = angles.target_speed_2 * degree_per_sec_factor
        p = self.current_point()
        return (pan_speed == 0 == tilt_speed
                or (p.pan_angle == pan_angle and p.tilt_angle == tilt_angle))

    def _move_gimbal_to_current_point(self):
        if not self.is_end_of_path_reached():
            p = self.current_point()
            yaw_speed = int(60 / degree_per_sec_factor)
            pitch_speed = int(12 / degree_per_sec_factor)
            control_gimbal(
                yaw_mode=2, yaw_speed=yaw_speed, yaw_angle=p.pan_angle,
                pitch_mode=2, pitch_speed=pitch_speed, pitch_angle=p.tilt_angle)


def _print_angles(angles: GetAnglesInCmd):
    column_names = ('imu_angle', 'target_angle', 'target_speed')
    print('\t'.join(column_names))
    # noinspection Mypy
    for imu_angle, target_angle, target_speed in grouper(angles, 3):
        print('\t'.join((
            f'{imu_angle * degree_factor:{len(column_names[0]) - 1}.2f}°',
            f'{target_angle * degree_factor:{len(column_names[1]) - 1}.2f}°',
            f'{target_speed * degree_per_sec_factor:{len(column_names[2]) - 3}.2f}°/s'
        )))


def _main():
    from time import sleep
    connection = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=10)
    controller = BaseCamPathOfMotionCameraController(connection)
    controller.add_point(PointOfMotion(pan_angle=0, tilt_angle=0))
    controller.add_point(PointOfMotion(pan_angle=180, tilt_angle=30))
    controller.add_point(PointOfMotion(pan_angle=0, tilt_angle=0))
    camera_speeds = CameraSpeeds()
    controller.start()
    while not controller.is_end_of_path_reached():
        sleep(1 / 15)
        controller.update(camera_speeds)


if __name__ == '__main__':
    _main()
