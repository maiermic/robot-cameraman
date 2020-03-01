import struct
from collections import namedtuple
from logging import getLogger

import serial

from simplebgc.command_ids import *
from simplebgc.commands import ControlOutCmd, RawCmd

logger = getLogger(__name__)

MessageHeader = namedtuple(
    'MessageHeader',
    'start_character command_id payload_size header_checksum')

MessagePayload = namedtuple(
    'MessagePayload',
    'payload payload_checksum')

Message = namedtuple(
    'Message',
    'start_character command_id payload_size header_checksum payload payload_checksum')

# The following factor is used to convert degrees to the units used by the
# SimpleBGC 2.6 serial protocol.
degree_factor = 0.02197265625
degree_per_sec_factor = 0.1220740379


def create_message(command_id: int, payload: bytes = b'') -> Message:
    payload_size = len(payload)
    return Message(start_character=ord('>'),
                   command_id=command_id,
                   payload_size=payload_size,
                   header_checksum=(command_id + payload_size) % 256,
                   payload=payload,
                   payload_checksum=sum(payload) % 256)


def pack_message(message: Message) -> bytes:
    message_format = '<BBBB{}sB'.format(message.payload_size)
    return struct.pack(message_format, *message)


def unpack_message(data: bytes, payload_size: int) -> Message:
    message_format = '<BBBB{}sB'.format(payload_size)
    return Message._make(struct.unpack(message_format, data))


def read_message(connection: serial.Serial, payload_size: int) -> Message:
    # 5 is the length of the header + payload checksum byte
    # 1 is the payload size
    response_data = connection.read(5 + payload_size)
    # print('received response', response_data)
    return unpack_message(response_data, payload_size)


def read_message_header(connection: serial.Serial) -> MessageHeader:
    header_data = connection.read(4)
    logger.debug(f'received message header data: {header_data}')
    return MessageHeader._make(struct.unpack('<BBBB', header_data))


def read_message_payload(connection: serial.Serial,
                         payload_size: int) -> MessagePayload:
    # +1 because of payload checksum
    payload_data = connection.read(payload_size + 1)
    logger.debug(f'received message payload data: {payload_data}')
    payload_format = '<{}sB'.format(payload_size)
    return MessagePayload._make(struct.unpack(payload_format, payload_data))


def read_cmd(connection: serial.Serial) -> RawCmd:
    header = read_message_header(connection)
    logger.debug(f'parsed message header: {header}')
    assert header.start_character == 62
    checksum = (header.command_id + header.payload_size) % 256
    assert checksum == header.header_checksum
    payload = read_message_payload(connection, header.payload_size)
    logger.debug(f'parsed message payload: {payload}')
    assert sum(payload.payload) % 256 == payload.payload_checksum
    return RawCmd(header.command_id, payload.payload)


def control_gimbal(
        yaw_mode: int = 1,
        yaw_speed: int = 0,
        yaw_angle: int = 0,
        pitch_mode: int = 1,
        pitch_speed: int = 0,
        pitch_angle: int = 0) -> None:
    logger.debug(' '.join((
        f'control_gimbal:',
        f'yaw_mode={yaw_mode}',
        f'yaw_speed={yaw_speed}',
        f'yaw_angle={yaw_angle}',
        f'pitch_mode={pitch_mode}',
        f'pitch_speed={pitch_speed}',
        f'pitch_angle={pitch_angle}')))
    yaw_angle = int(yaw_angle / degree_factor)
    pitch_angle = int(pitch_angle / degree_factor)
    control_data = ControlOutCmd(
        roll_mode=2, roll_speed=0, roll_angle=0,
        pitch_mode=pitch_mode, pitch_speed=pitch_speed, pitch_angle=pitch_angle,
        yaw_mode=yaw_mode, yaw_speed=yaw_speed, yaw_angle=yaw_angle)
    message = create_message(CMD_CONTROL, control_data.pack())
    packed_message = pack_message(message)
    connection = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=10)
    connection.write(packed_message)
    message = read_message(connection, 1)


if __name__ == '__main__':
    from time import sleep

    # rotate_gimbal(yaw_speed=-100)
    # rotate_gimbal(yaw_speed=100)
    # sleep(3)
    # rotate_gimbal(yaw_speed=0)
    control_gimbal(
        pitch_mode=2, pitch_speed=300, pitch_angle=0,
        yaw_mode=2, yaw_speed=300, yaw_angle=0)
    sleep(3)
    control_gimbal(
        pitch_mode=2, pitch_speed=300, pitch_angle=-60,
        yaw_mode=2, yaw_speed=300, yaw_angle=360)
    sleep(3)
    control_gimbal(
        pitch_mode=2, pitch_speed=300, pitch_angle=0,
        yaw_mode=2, yaw_speed=300, yaw_angle=0)

# 1u – 1 byte unsigned
# 1s – 1 byte signed
# 2u – 2 byte unsigned (little-endian order)
# 2s – 2 byte signed (little-endian order)
# 4f – float (IEEE-754 standard)
# 4s – 4 bytes signed (little-endian order)
# string – ASCII character array, first byte is array size
# Nb – byte array size N

# CMD_BOARD_INFO
# >   id  size  check  payload  check
# 62  86    1    87       1       1
# 62  86    0    86              0
