import io
import logging
import socket
from logging import Logger

from pathlib import Path
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


class FileLiveView(LiveView):
    @staticmethod
    def get_image_size(video_or_image_file):
        video = cv2.VideoCapture(video_or_image_file)
        height = video.get(cv2.CAP_PROP_FRAME_HEIGHT)
        width = video.get(cv2.CAP_PROP_FRAME_WIDTH)
        return ImageSize(int(width), int(height))

    _previous_image: Optional[Image]

    def __init__(self, file: Path) -> None:
        self._previous_image = None
        self._file = file
        self._video_stream = cv2.VideoCapture(str(self._file))
        self._frame_count = self._get_frame_count()
        self._is_play = True
        self._frame_index = 0

    def _get_frame_count(self):
        vs = cv2.VideoCapture(str(self._file))
        frame_count = int(vs.get(cv2.CAP_PROP_FRAME_COUNT))
        if (frame_count != 0):
            return frame_count
        logger.warning(
            'CAP_PROP_FRAME_COUNT not available => counting frames...')
        while True:
            success, frame = vs.read()
            if success:
                frame_count += 1
            else:
                break
        return frame_count

    def image(self) -> Optional[Image]:
        success, image = False, None
        if self._is_play:
            self._video_stream.set(cv2.CAP_PROP_POS_FRAMES, self._frame_index)
            success, image = self._video_stream.read()
            self._is_play = False
        if not success or image is None:
            if self._previous_image is None:
                return None
            return self._previous_image.copy()
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self._previous_image = PIL.Image.fromarray(rgb_image)
        return self._previous_image.copy()

    def next_frame(self):
        self._is_play = True
        if (self._frame_index + 1) < self._frame_count:
            self._frame_index += 1
        print(f'{self._frame_index}/{self._frame_count}')

    def previous_frame(self):
        self._is_play = True
        if 0 <= (self._frame_index - 1):
            self._frame_index -= 1
        print(f'{self._frame_index}/{self._frame_count}')

    def start_frame(self):
        self._is_play = True
        self._frame_index = 0

    def end_frame(self):
        self._is_play = True
        self._frame_index = self._frame_count - 1


class DummyLiveView(LiveView):
    def __init__(self, size: ImageSize) -> None:
        self._image = PIL.Image.new('RGB', size, (228, 150, 150))

    def image(self) -> Optional[Image]:
        sleep(0.2)
        return self._image
