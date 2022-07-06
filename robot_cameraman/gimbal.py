from abc import abstractmethod
from typing_extensions import Protocol

import simplebgc.gimbal
from simplebgc.commands import GetAnglesInCmd
from simplebgc.gimbal import ControlMode


# TODO interface should be independent from simplebgc module,
#   since other gimbals might use different modes or values
class Gimbal(Protocol):
    @abstractmethod
    def control(
            self,
            yaw_mode: ControlMode = ControlMode.speed,
            yaw_speed: float = 0,
            yaw_angle: float = 0,
            pitch_mode: ControlMode = ControlMode.speed,
            pitch_speed: float = 0,
            pitch_angle: float = 0,
            roll_mode: ControlMode = ControlMode.speed,
            roll_speed: float = 0,
            roll_angle: float = 0) -> None:
        # TODO add missing parameter documentation
        """Control the gimbal.

        :param yaw_mode:
        :param yaw_speed: Speed in degree per second. Positive values mean
         clockwise, negative values stand for counter clockwise moving
         direction from the camera's point of view.
        :param yaw_angle:
        :param pitch_mode:
        :param pitch_speed: Speed in degree per second. Positive values mean
         upwards, negative values stand for downwards moving direction from the
         camera's point of view.
        :param pitch_angle:
        :param roll_mode:
        :param roll_speed:
        :param roll_angle:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_angles(self) -> GetAnglesInCmd:
        raise NotImplementedError


class SimpleBgcGimbal(simplebgc.gimbal.Gimbal, Gimbal):
    pass


class TiltInvertedGimbal(Gimbal):
    """Wrap another gimbal to invert its tilt direction.
    If the camera is mounted on the gimbal in the opposite direction (rotated
    180 degree), the tilt speed and angle has to be inverted.

    See https://github.com/maiermic/robot-cameraman/issues/46
    """

    def __init__(self, gimbal: Gimbal) -> None:
        self._gimbal = gimbal

    def control(self, yaw_mode: ControlMode = ControlMode.speed,
                yaw_speed: float = 0, yaw_angle: float = 0,
                pitch_mode: ControlMode = ControlMode.speed,
                pitch_speed: float = 0, pitch_angle: float = 0,
                roll_mode: ControlMode = ControlMode.speed,
                roll_speed: float = 0, roll_angle: float = 0) -> None:
        self._gimbal.control(yaw_mode, yaw_speed, yaw_angle,
                             # invert speed and angle
                             pitch_mode, -pitch_speed, -pitch_angle,
                             roll_mode, roll_speed, roll_angle)

    def stop(self) -> None:
        self._gimbal.stop()

    def get_angles(self) -> GetAnglesInCmd:
        angles = self._gimbal.get_angles()
        return GetAnglesInCmd(
            imu_angle_1=angles.imu_angle_1,
            target_angle_1=angles.target_angle_1,
            target_speed_1=angles.target_speed_1,
            imu_angle_2=angles.imu_angle_2,
            # invert tilt speed and angle
            target_angle_2=-angles.target_angle_2,
            target_speed_2=-angles.target_speed_2,
            imu_angle_3=angles.imu_angle_3,
            target_angle_3=angles.target_angle_3,
            target_speed_3=angles.target_speed_3)


class DummyGimbal(Gimbal):
    def control(self, yaw_mode: ControlMode = ControlMode.speed,
                yaw_speed: float = 0, yaw_angle: float = 0,
                pitch_mode: ControlMode = ControlMode.speed,
                pitch_speed: float = 0, pitch_angle: float = 0,
                roll_mode: ControlMode = ControlMode.speed,
                roll_speed: float = 0, roll_angle: float = 0) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_angles(self) -> GetAnglesInCmd:
        return GetAnglesInCmd(
            imu_angle_1=0,
            target_angle_1=0,
            target_speed_1=0,
            imu_angle_2=0,
            target_angle_2=0,
            target_speed_2=0,
            imu_angle_3=0,
            target_angle_3=0,
            target_speed_3=0)
