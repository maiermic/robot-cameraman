from __future__ import annotations

import logging
import socket
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import Logger
from typing import Union, List, Tuple, Iterator, Any, Optional

logger: Logger = logging.getLogger(__name__)


@dataclass()
class BytesReader:
    data: bytes
    i: int = 0

    def read(self, length):
        start = self.i
        end = self.i + length
        assert end <= len(self.data), \
            f'not enough bytes to read {length}: read {self.i} of {len(self.data)} bytes from {self}'
        self.i = end
        return self.data[start:end]

    def unpack(self, format: Union[bytes, str]):
        s = struct.Struct(format)
        return s.unpack(self.read(s.size))


@dataclass()
class BasicHeader:
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

    @classmethod
    def unpack(cls, reader: BytesReader):
        return cls(*reader.unpack('>HHib6sbbbi8sH'))


@dataclass
class C1488o:
    rectangle: Tuple[int, int, int, int]
    color: Tuple[int, int, int]
    c: int


# noinspection Mypy
@dataclass()
class ExHeader(ABC):
    @classmethod
    @abstractmethod
    def unpack_params(cls, ex_header_data: BytesReader) -> Iterator[Any]:
        pass

    @classmethod
    def unpack(cls, ex_header_data: BytesReader):
        # noinspection Mypy,PyArgumentList
        return cls(*cls.unpack_params(ex_header_data))


@dataclass()
class ExHeader1(ExHeader):
    zoomRatio: int
    b: int
    c: int
    zoomRatioPos: int
    e: int
    f: int
    g: int
    h: int
    i: int
    j: int
    k: int
    l: int
    m: int
    n: List[C1488o]

    @classmethod
    def unpack_params(cls, ex_header_data: BytesReader):
        head = ex_header_data.unpack('>H12B')
        m = head[-1]
        n: List[C1488o] = []
        for _ in range(m):
            left, top, right, bottom, r, g, b, c = \
                ex_header_data.unpack('>4H4B')
            n.append(C1488o(rectangle=(left, top, right, bottom),
                            color=(r & 255, g & 255, b & 255),
                            c=c))
        yield from head
        yield n


@dataclass()
class ExHeader2(ExHeader):
    zoomRatio: int
    b: int
    c: int
    zoomRatioPos: int
    e: int
    f: int
    g: int
    h: int
    i: int

    @classmethod
    def unpack_params(cls, ex_header_data: BytesReader) -> Iterator[Any]:
        yield from ex_header_data.unpack('>H8B')


@dataclass()
class ExHeader3(ExHeader):
    formatTag: int
    channels: int
    samplesPerSec: int
    avgBytePerSec: int
    blockAlign: int
    bitsPerSample: int
    channelMask: int
    exReserve1: int

    @classmethod
    def unpack_params(cls, ex_header_data: BytesReader) -> Iterator[Any]:
        yield from ex_header_data.unpack('>HHiiHHiH')


@dataclass()
class ExHeader5(ExHeader1):
    p: int
    q: int
    r: int
    s: int
    t: int
    u: int
    v: int
    w: int
    x: int
    y: int
    z: int
    A: int
    B: int
    C: int
    D: int
    E: int
    F: int
    G: int
    H: int
    I: int
    J: int
    K: int
    L: int
    M: List[int]

    @classmethod
    def unpack_params(cls, ex_header_data: BytesReader):
        yield from super().unpack_params(ex_header_data)
        head = ex_header_data.unpack('>18HB3HB')
        L = head[-1]
        M: List[int] = []
        for _ in range(L):
            M.append(ex_header_data.unpack('>B')[0])
        # noinspection Mypy
        yield from head
        yield M


@dataclass
class ExHeader6(ExHeader5):
    O: int

    @classmethod
    def unpack_params(cls, ex_header_data: BytesReader):
        yield from super().unpack_params(ex_header_data)
        O = ex_header_data.unpack('>B')
        # noinspection Mypy
        yield O


@dataclass
class ExHeader8(ExHeader6):
    Q: int
    R: int
    S: int

    @classmethod
    def unpack_params(cls, ex_header_data: BytesReader):
        yield from super().unpack_params(ex_header_data)
        yield from ex_header_data.unpack('>H2B')


@dataclass()
class ExHeader11(ExHeader2):
    k: int
    l: int
    m: int
    n: int
    o: int

    @classmethod
    def unpack_params(cls, ex_header_data: BytesReader) -> Iterator[Any]:
        yield from ex_header_data.unpack('>H7B')
        yield 0  # inherited field i is not read from header data
        yield from ex_header_data.unpack('>5B')


class LiveView:
    def __init__(self, ip: str, port: int) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ip, port))
        self.sock.settimeout(0.5)
        self._header_listeners = []

    def add_ex_header_listener(self, callback):
        self._header_listeners.append(callback)

    def _notify_ex_header_listeners(self, ex_header: ExHeader):
        for listener in self._header_listeners:
            listener(ex_header)

    def image(self) -> bytes:
        """
        Read image data from socket.

        Example:
            PIL.Image.open(io.BytesIO(live_view.image()))

        :return: Image data
        """
        bufsize = 65536
        data, addr = self.sock.recvfrom(bufsize)
        reader = BytesReader(data)
        bhs = 32  # basic header size
        # TODO check pts is parsed correctly
        basic_header = BasicHeader.unpack(reader)
        ehs = basic_header.exHeaderSize
        if ehs > 0:
            ex_header_type, = reader.unpack('>H')
            ex_header: Optional[ExHeader] = None
            if ex_header_type == 3:
                ex_header = ExHeader3.unpack(reader)
            elif ex_header_type == 8:
                ex_header = ExHeader8.unpack(reader)
            elif ex_header_type == 11:
                ex_header = ExHeader11.unpack(reader)
                reader.read(8)  # probably reserved data
            else:
                logger.warning('unhandled ex header type %d', ex_header_type)
            logger.debug(f'ex header: {ex_header}')
            self._notify_ex_header_listeners(ex_header)
        offset = bhs + ehs
        if offset != reader.i:
            logger.warning('offsets differ: %d != %d', offset, reader.i)
        length = basic_header.totalSize - offset
        image_data = data[offset:]
        if len(image_data) != length:
            logger.warning('lengths differ: %d != %d', len(image_data), length)
        else:
            logger.debug(f'image data length: {len(image_data)}')
        return image_data


def _main():
    from panasonic_camera.camera_manager import PanasonicCameraManager
    import argparse
    import threading
    import signal
    import PIL.Image
    import io
    import os
    import cv2
    import numpy
    import logging
    import time
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(
        description="Detect objects in a video file using Google Coral USB.")
    parser.add_argument('--ip', type=str,
                        default='0.0.0.0',
                        help="UDP Socket IP address.")
    parser.add_argument('--port', type=int,
                        default=49199,
                        help="UDP Socket port.")
    args = parser.parse_args()

    to_exit = threading.Event()

    def quit(sig=None, frame=None):
        print("Exiting...")
        to_exit.set()
        if threading.current_thread() != camera_manager:
            print('wait for camera manager thread')
            camera_manager.cancel()
            camera_manager.join()
        exit(0)

    signal.signal(signal.SIGINT, quit)
    signal.signal(signal.SIGTERM, quit)

    camera_manager = PanasonicCameraManager()
    camera_manager.start()
    live_view = LiveView(args.ip, args.port)
    while not to_exit.is_set():
        try:
            if not camera_manager.is_stream_started:
                logger.debug('camera stream has not been started yet')
                time.sleep(0.2)
                continue
            image = PIL.Image.open(io.BytesIO(live_view.image()))
            if 'DISPLAY' in os.environ:
                cv2_image = cv2.cvtColor(numpy.asarray(image),
                                         cv2.COLOR_RGB2BGR)
                cv2.imshow('Live View', cv2_image)
                key = cv2.waitKey(5) & 0xFF
                if key == ord('q'):
                    logger.debug('key pressed to quit')
                    to_exit.set()
        except (socket.timeout, OSError) as e:
            logger.error(f'error reading live view image: {e}')
        except KeyboardInterrupt:
            break
    quit()


if __name__ == '__main__':
    _main()
