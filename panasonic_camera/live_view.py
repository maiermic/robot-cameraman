import socket


class LiveView:
    def __init__(self, ip, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ip, port))

    def image(self) -> bytes:
        """
        Read image data from socket.

        Example:
            PIL.Image.open(io.BytesIO(live_view.image()))

        :return: Image data
        """
        bufsize = 30000
        offset = 132
        data, addr = self.sock.recvfrom(bufsize)
        for i in range(130, 320):
            if data[i] == 0xFF and data[i + 1] == 0xD8:
                offset = i
                break
        return data[offset:]
