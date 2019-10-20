import logging
from abc import abstractmethod
from logging import Logger
from time import time

import numpy
import serial
from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from robot_cameraman.tracking import CameraSpeeds
from simplebgc.serial_example import control_gimbal, rotate_gimbal

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
    acceleration_per_second: int = 1000
    target_speed: int = 0
    current_speed: int = 0
    _elapsed_time: ElapsedTime

    def __init__(self):
        self._elapsed_time: ElapsedTime = ElapsedTime()

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

    def __init__(self, camera_manager: PanasonicCameraManager):
        self._camera_manager = camera_manager
        self._rotate_speed_manager = SpeedManager()
        self._tilt_speed_manager = SpeedManager()

    def start(self) -> None:
        self._rotate_speed_manager.reset()
        self._tilt_speed_manager.reset()

    def update(self, camera_speeds: CameraSpeeds) -> None:
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
        except serial.serialutil.SerialException:
            logger.error('failed to control gimbal')
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
