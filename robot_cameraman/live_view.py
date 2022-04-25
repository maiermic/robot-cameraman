import io
import logging
import socket
from logging import Logger
from typing import Optional

import PIL.Image
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFile
import PIL.ImageFont
import cv2
from PIL.Image import Image
from typing_extensions import Protocol

logger: Logger = logging.getLogger(__name__)


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
