import socket
import logging
from logging import Logger

logger: Logger = logging.getLogger(__name__)


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
        bufsize = 30000
        offset = 132
        logger.debug('receive image')
        data, addr = self.sock.recvfrom(bufsize)
        logger.debug('image received')
        for i in range(130, 320):
            if data[i] == 0xFF and data[i + 1] == 0xD8:
                offset = i
                break
        return data[offset:]
