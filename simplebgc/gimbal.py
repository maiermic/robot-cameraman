from enum import IntEnum
from logging import getLogger

from serial import Serial

from simplebgc.command_ids import CMD_CONTROL, CMD_GET_ANGLES, CMD_CONFIRM
from simplebgc.command_parser import parse_cmd
from simplebgc.commands import ControlOutCmd, GetAnglesInCmd
from simplebgc.serial_example import create_message, \
    pack_message, read_message, Message, read_cmd
from simplebgc.units import from_degree_per_sec, from_degree

logger = getLogger(__name__)


class ControlMode(IntEnum):
    """Modes of the outgoing command CMD_CONTROL
    """
    no_control = 0
    speed = 1
    angle = 2
    speed_angle = 3
    rc = 4
    rc_high_res = 6
    angle_rel_frame = 5
    # TODO flags


class Gimbal:

    def __init__(self, connection: Serial = None) -> None:
        if connection is None:
            connection = Serial('/dev/ttyUSB0', baudrate=115200, timeout=10)
        self._connection = connection

    def send_message(self, message: Message):
        logger.debug(f'send message: {message}')
        self._connection.write(pack_message(message))

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
            roll_angle: float = 0):
        control_data = ControlOutCmd(
            roll_mode=int(roll_mode),
            roll_speed=from_degree_per_sec(roll_speed),
            roll_angle=from_degree(roll_angle),
            pitch_mode=int(pitch_mode),
            pitch_speed=from_degree_per_sec(pitch_speed),
            pitch_angle=from_degree(pitch_angle),
            yaw_mode=int(yaw_mode),
            yaw_speed=from_degree_per_sec(yaw_speed),
            yaw_angle=from_degree(yaw_angle))
        logger.debug(f'send control cmd: {control_data}')
        message = create_message(CMD_CONTROL, control_data.pack())
        self.send_message(message)
        confirmation: Message = read_message(self._connection, 1)
        assert confirmation.command_id == CMD_CONFIRM, \
            f'expected confirmation, but received command with ID' \
            f' {confirmation.command_id}'

    def stop(self):
        self.control(roll_mode=ControlMode.no_control,
                     pitch_mode=ControlMode.no_control,
                     yaw_mode=ControlMode.no_control)

    def get_angles(self) -> GetAnglesInCmd:
        self.send_message(create_message(CMD_GET_ANGLES))
        cmd = read_cmd(self._connection)
        assert cmd.id == CMD_GET_ANGLES
        return parse_cmd(cmd)


def _main():
    from time import sleep
    import logging
    logging.basicConfig(level=logging.DEBUG)
    gimbal = Gimbal()
    pitch_speed = 12
    yaw_speed = 60
    gimbal.control(
        pitch_mode=ControlMode.angle, pitch_speed=pitch_speed, pitch_angle=0,
        yaw_mode=ControlMode.angle, yaw_speed=yaw_speed, yaw_angle=0)
    sleep(3)
    gimbal.control(
        pitch_mode=ControlMode.angle, pitch_speed=pitch_speed, pitch_angle=-60,
        yaw_mode=ControlMode.angle, yaw_speed=yaw_speed, yaw_angle=360)
    sleep(3)
    gimbal.control(
        pitch_mode=ControlMode.angle, pitch_speed=pitch_speed, pitch_angle=0,
        yaw_mode=ControlMode.angle, yaw_speed=yaw_speed, yaw_angle=0)


if __name__ == '__main__':
    _main()
