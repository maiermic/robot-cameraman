import re
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

import PIL.Image


@dataclass
class ImageContainer:
    image: Optional[PIL.Image.Image]


class RobotCameramanHttpHandler(BaseHTTPRequestHandler):
    # static members
    to_exit: threading.Event
    server_image: ImageContainer

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
                self.wfile.write(str.encode("\r\n--jpgboundary\r\n"))
                self.send_header('Content-type', 'image/jpeg')
                self.send_header('Content-length', len(jpg_bytes))
                self.end_headers()
                jpg.save(self.wfile, 'JPEG')
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
            if action == 'left':
                print('left')
            if action == 'right':
                print('right')
            if action == 'stop':
                print('stop')
            self.send_response(200)
            self.end_headers()
            return
