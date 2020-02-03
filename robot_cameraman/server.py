import threading
from dataclasses import dataclass
from io import BytesIO
from logging import Logger, getLogger
from typing import Optional

import PIL.Image
from flask import Flask, render_template, Response

from robot_cameraman.cameraman_mode_manager import CameramanModeManager

logger: Logger = getLogger(__name__)


@dataclass
class ImageContainer:
    image: Optional[PIL.Image.Image]


to_exit: threading.Event
server_image: ImageContainer
cameraman_mode_manager: CameramanModeManager

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/start_tracking')
def start_tracking():
    logger.debug('start tracking')
    cameraman_mode_manager.tracking_mode()
    return '', 204


@app.route('/api/left')
def manually_rotate_left():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually rotate left')
    cameraman_mode_manager.manual_rotate(-100)
    return '', 204


@app.route('/api/right')
def manually_rotate_right():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually rotate right')
    cameraman_mode_manager.manual_rotate(100)
    return '', 204


@app.route('/api/tilt_up')
def manually_tilt_up():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually tilt up')
    cameraman_mode_manager.manual_tilt(-100)
    return '', 204


@app.route('/api/tilt_down')
def manually_tilt_down():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually tilt down')
    cameraman_mode_manager.manual_tilt(100)
    return '', 204


@app.route('/api/zoom_out')
def manually_zoom_out():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually zoom out')
    cameraman_mode_manager.manual_zoom(-200)
    return '', 204


@app.route('/api/zoom_in')
def manually_zoom_in():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually zoom in')
    cameraman_mode_manager.manual_zoom(200)
    return '', 204


@app.route('/api/stop')
def manually_stop():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually stop')
    cameraman_mode_manager.stop_camera()
    return '', 204


def stream_frames():
    """Read live view frames regularly."""
    # TODO synchronize with source (do not send the same image twice)
    while not to_exit.wait(0.05):
        jpg = server_image.image
        buffered = BytesIO()
        jpg.save(buffered, format="JPEG")
        frame = buffered.getvalue()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/cam.mjpg')
def live_view():
    """Stream live view image of camera."""
    return Response(stream_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def run_server(_to_exit: threading.Event,
               _cameraman_mode_manager: CameramanModeManager,
               _server_image: ImageContainer):
    # TODO use dependency injection instead of global variables
    global to_exit, cameraman_mode_manager, server_image
    to_exit = _to_exit
    cameraman_mode_manager = _cameraman_mode_manager
    server_image = _server_image
    app.run(host='0.0.0.0', port=9000, threaded=True)
