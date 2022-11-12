import io
import logging
import socket
from logging import Logger
from time import sleep
from typing import Optional, NamedTuple

import PIL.Image
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFile
import PIL.ImageFont
import cv2
import PIL
from PIL.Image import Image
from typing_extensions import Protocol

logger: Logger = logging.getLogger(__name__)

ImageSize = NamedTuple('ImageSize', [
    ('width', int),
    ('height', int),
])


class LiveView(Protocol):
    def image(self) -> Optional[Image]:
        raise NotImplementedError


class PanasonicLiveView(LiveView):
    def __init__(self, ip: str, port: int) -> None:
        import panasonic_camera.live_view
        self._live_view = panasonic_camera.live_view.LiveView(ip, port)

    def add_ex_header_listener(self, callback):
        self._live_view.add_ex_header_listener(callback)

    def image(self) -> Optional[Image]:
        try:
            return PIL.Image.open(io.BytesIO(self._live_view.image()))
        except (socket.timeout, OSError) as e:
            logger.error(f'error reading live view image: {e}')
        return None


class WebcamLiveView(LiveView):
    def __init__(self) -> None:
        from imutils.video import VideoStream
        self._video_stream = VideoStream(src=0).start()

    def image(self) -> Optional[Image]:
        image = self._video_stream.read()
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return PIL.Image.fromarray(rgb_image)


class DummyLiveView(LiveView):
    def __init__(self, size: ImageSize) -> None:
        self._image = PIL.Image.new('RGB', size, (228, 150, 150))

    def image(self) -> Optional[Image]:
        sleep(0.2)
        return self._image


class DummyWithTargetsLiveView(LiveView):
    def __init__(self, size: ImageSize) -> None:
        self._size = size

    def image(self) -> Optional[Image]:
        sleep(0.2)
        image = PIL.Image.new('RGB', self._size, (228, 150, 150))
        draw = PIL.ImageDraw.Draw(image)
        draw.rectangle((15, 30, 50, 100), fill=(0, 0, 255))
        draw.rectangle((350, 300, 450, 400), fill=(255, 0, 255))
        return image
