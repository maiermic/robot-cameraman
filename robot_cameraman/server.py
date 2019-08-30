import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from typing import Optional

import PIL.Image


@dataclass
class ImageContainer:
    image: Optional[PIL.Image.Image]


class RobotCameramanHttpHandler(BaseHTTPRequestHandler):
    # static members
    to_exit: threading.Event
    server_image: ImageContainer

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
        if self.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write("""
                    <html>
                        <head></head>
                        <body><img src="cam.mjpg"/></body>
                    </html>
                """.encode())
            return
