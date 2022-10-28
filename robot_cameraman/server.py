import enum
import threading
from dataclasses import dataclass
from io import BytesIO
from logging import Logger, getLogger
from pathlib import Path
from typing import Optional

import PIL.Image
from flask import Flask, Response, request, redirect, jsonify

from robot_cameraman.cameraman_mode_manager import CameramanModeManager
from robot_cameraman.camera_speeds import ZoomSpeed, CameraSpeeds
from robot_cameraman.ui import StatusBar
from robot_cameraman.updatable_configuration import UpdatableConfiguration

logger: Logger = getLogger(__name__)


class ServerImageSource(enum.Enum):
    LIVE_VIEW = enum.auto()
    COLOR_MASK = enum.auto()


@dataclass
class ImageContainer:
    image: Optional[PIL.Image.Image]
    source: ServerImageSource = ServerImageSource.LIVE_VIEW


to_exit: threading.Event
server_image: ImageContainer
manual_camera_speeds: CameraSpeeds
updatable_configuration: UpdatableConfiguration
status_bar: StatusBar
cameraman_mode_manager: CameramanModeManager

app = Flask(__name__,
            static_url_path='',
            static_folder=Path(__file__).parent / 'server_static_folder')


@app.route('/')
def index():
    return redirect('index.html')


@app.route('/api/start_tracking')
def start_tracking():
    logger.debug('start tracking')
    cameraman_mode_manager.tracking_mode()
    return '', 204


@app.route('/api/left')
def manually_rotate_left():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually rotate left')
    cameraman_mode_manager.manual_rotate(-manual_camera_speeds.pan_speed)
    return '', 204


@app.route('/api/right')
def manually_rotate_right():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually rotate right')
    cameraman_mode_manager.manual_rotate(manual_camera_speeds.pan_speed)
    return '', 204


@app.route('/api/tilt_up')
def manually_tilt_up():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually tilt up')
    cameraman_mode_manager.manual_tilt(manual_camera_speeds.tilt_speed)
    return '', 204


@app.route('/api/tilt_down')
def manually_tilt_down():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually tilt down')
    cameraman_mode_manager.manual_tilt(-manual_camera_speeds.tilt_speed)
    return '', 204


@app.route('/api/zoom_out')
def manually_zoom_out():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually zoom out')
    cameraman_mode_manager.manual_zoom(
        ZoomSpeed(-manual_camera_speeds.zoom_speed))
    return '', 204


@app.route('/api/zoom_in')
def manually_zoom_in():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually zoom in')
    cameraman_mode_manager.manual_zoom(manual_camera_speeds.zoom_speed)
    return '', 204


@app.route('/api/stop')
def manually_stop():
    cameraman_mode_manager.manual_mode()
    logger.debug('manually stop')
    cameraman_mode_manager.stop_camera()
    return '', 204


@app.route('/api/angle')
def angle():
    if 'pan' not in request.args:
        return "Missing query parameter 'pan'", 400
    if 'tilt' not in request.args:
        return "Missing query parameter 'tilt'", 400
    try:
        pan_angle = int(request.args.get('pan'))
    except ValueError:
        return "Query parameter 'pan' should be a number", 400
    try:
        tilt_angle = int(request.args.get('tilt'))
    except ValueError:
        return "Query parameter 'tilt' should be a number", 400
    logger.debug(f'angle pan={pan_angle} tilt={tilt_angle}')
    cameraman_mode_manager.angle(pan_angle=pan_angle, tilt_angle=tilt_angle)
    return '', 204


@app.route('/api/status-bar', methods=['GET'])
def get_status_bar():
    global status_bar
    return status_bar.text, 200


@app.route('/api/configuration', methods=['GET'])
def get_configuration():
    global updatable_configuration
    return jsonify(updatable_configuration.configuration)


@app.route('/api/configuration', methods=['PUT'])
def update_configuration():
    global updatable_configuration
    if 'tracking' in request.json:
        tracking = request.json['tracking']
        if 'color' in tracking:
            color = tracking['color']
            if 'min_hsv' in color:
                updatable_configuration.update_tracking_color(
                    min_hsv=color['min_hsv'])
            if 'max_hsv' in color:
                updatable_configuration.update_tracking_color(
                    max_hsv=color['max_hsv'])
    if 'limits' in request.json:
        updatable_configuration.update_limits(request.json['limits'])
    return '', 200


@app.route('/api/live-view/source', methods=['PUT'])
def update_live_view_source():
    global server_image
    if request.json == 'LIVE_VIEW':
        server_image.source = ServerImageSource.LIVE_VIEW
    elif request.json == 'COLOR_MASK':
        server_image.source = ServerImageSource.COLOR_MASK
    else:
        return f"unknown source {request.json}", 400
    return '', 200


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
               _server_image: ImageContainer,
               _manual_camera_speeds: CameraSpeeds,
               _updatable_configuration: UpdatableConfiguration,
               _status_bar: StatusBar,
               ssl_certificate: Path,
               ssl_key: Path):
    # TODO use dependency injection instead of global variables
    global to_exit, cameraman_mode_manager, server_image, manual_camera_speeds, \
        updatable_configuration, status_bar
    to_exit = _to_exit
    cameraman_mode_manager = _cameraman_mode_manager
    server_image = _server_image
    manual_camera_speeds = _manual_camera_speeds
    updatable_configuration = _updatable_configuration
    status_bar = _status_bar
    app.run(host='0.0.0.0', port=9000, threaded=True,
            ssl_context=(ssl_certificate, ssl_key))
