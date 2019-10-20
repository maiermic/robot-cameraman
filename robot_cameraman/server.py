import logging
import re
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from logging import Logger
from pathlib import Path
from typing import Optional

import PIL.Image

from robot_cameraman.cameraman_mode_manager import CameramanModeManager

logger: Logger = logging.getLogger(__name__)


@dataclass
class ImageContainer:
    image: Optional[PIL.Image.Image]


class RobotCameramanHttpHandler(BaseHTTPRequestHandler):
    # static members
    to_exit: threading.Event
    server_image: ImageContainer
    cameraman_mode_manager: CameramanModeManager

    # type hints
    path: str

    api_regex = re.compile(r'/api/(\w+)')

    def do_GET(self):
        if self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Content-type',
                             'multipart/x-mixed-replace; boundary=jpgboundary')
            self.end_headers()
            while not self.to_exit.wait(0.05):
                jpg = self.server_image.image
                jpg_bytes = jpg.tobytes()
                try:
                    self.wfile.write(str.encode("\r\n--jpgboundary\r\n"))
                    self.send_header('Content-type', 'image/jpeg')
                    self.send_header('Content-length', len(jpg_bytes))
                    self.end_headers()
                    jpg.save(self.wfile, 'JPEG')
                except ConnectionResetError:
                    pass  # ignore
            return
        templates: Path = Path(__file__).parent / 'templates'
        if self.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write((templates / 'index.html').read_text().encode())
            return
        api_match = self.api_regex.fullmatch(self.path)
        if api_match:
            action = api_match.group(1)
            if action == 'start_tracking':
                self.cameraman_mode_manager.tracking_mode()
            else:
                self.cameraman_mode_manager.manual_mode()
                if action == 'left':
                    logger.debug('manually rotate left')
                    self.cameraman_mode_manager.manual_rotate(-100)
                elif action == 'right':
                    logger.debug('manually rotate right')
                    self.cameraman_mode_manager.manual_rotate(100)
                elif action == 'tilt_up':
                    logger.debug('manually tilt up')
                    self.cameraman_mode_manager.manual_tilt(-100)
                elif action == 'tilt_down':
                    logger.debug('manually tilt down')
                    self.cameraman_mode_manager.manual_tilt(100)
                elif action == 'zoom_out':
                    logger.debug('manually zoom out')
                    self.cameraman_mode_manager.manual_zoom(-200)
                elif action == 'zoom_in':
                    logger.debug('manually zoom in')
                    self.cameraman_mode_manager.manual_zoom(200)
                elif action == 'stop':
                    logger.debug('manually stop')
                    self.cameraman_mode_manager.stop()
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
            self.send_response(200)
            self.end_headers()
            return
