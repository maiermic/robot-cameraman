import logging
import socket
import struct
from logging import Logger
from typing import NamedTuple, Union

logger: Logger = logging.getLogger(__name__)


class BasicHeader(NamedTuple):
    totalSize: int
    version: int
    seqNo: int
    dataFlag: int
    srcID: int
    srcSubID: int
    dataType: int
    reserve1: int
    pts: int
    reserve2: int
    exHeaderSize: int


class ExHeader3(NamedTuple):
    formatTag: int
    channels: int
    samplesPerSec: int
    avgBytePerSec: int
    blockAlign: int
    bitsPerSample: int
    channelMask: int
    exReserve1: int


class ExHeader11(NamedTuple):
    zoomRatio: int
    b: int
    c: int
    zoomRatioPos: int
    e: int
    f: int
    g: int
    h: int
    # i: int
    k: int
    l: int
    m: int
    n: int
    o: int


class LiveView:
    def __init__(self, ip: str, port: int) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ip, port))
        self.sock.settimeout(0.5)

    def image(self) -> bytes:
        """
        Read image data from socket.

        Example:
            PIL.Image.open(io.BytesIO(live_view.image()))

        :return: Image data
        """
        bufsize = 65536
        data, addr = self.sock.recvfrom(bufsize)
        bhs = 32  # basic header size
        # TODO check pts is parsed correctly
        basic_header = BasicHeader._make(
            struct.unpack('>HHib6sbbbi8sH', data[:bhs]))
        ehs = basic_header.exHeaderSize
        if ehs > 0:
            ehts = 2  # ex header type size (short => 2 bytes)
            ex_header_type_data = data[bhs:bhs + ehts]
            ex_header_type, = struct.unpack('>H', ex_header_type_data)
            ex_header_data = data[(bhs + ehts):(bhs + ehs)]
            ex_header: Union[ExHeader3, ExHeader11, None] = None
            if ex_header_type == 3:
                ex_header = ExHeader3._make(
                    struct.unpack('>HHiiHHiH', ex_header_data))
            elif ex_header_type == 11:
                ex_header = ExHeader11._make(
                    struct.unpack('>H12B', ex_header_data[:14]))
            else:
                logger.warning('unhandled ex header type %d', ex_header_type)
            logger.debug(f'ex header: {ex_header}')
        offset = bhs + ehs
        length = basic_header.totalSize - offset
        image_data = data[offset:]
        if len(image_data) != length:
            logger.warning('lengths differ: %d != %d', len(image_data), length)
        else:
            logger.debug(f'image data length: {len(image_data)}')
        return image_data
