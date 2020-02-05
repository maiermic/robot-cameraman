import logging
import signal
import time
from logging import Logger
from typing import Optional
from urllib.parse import urlparse

import requests
import urllib3

from panasonic_camera.camera import PanasonicCamera, BusyError, CriticalError
from panasonic_camera.discover import discover_panasonic_camera_devices
from panasonic_camera.interval import signal_handler, IntervalThread, \
    ProgramKilled

logger: Logger = logging.getLogger(__name__)


class PanasonicCameraManager(IntervalThread):
    camera: Optional[PanasonicCamera]

    def __init__(self, interval=10, *_args, **_kwargs) -> None:
        super().__init__(interval, self._ensure_connection, *_args, **_kwargs)
        self.camera = None

    def _ensure_connection(self):
        if self.camera:
            try:
                logger.debug(self.camera.get_state().__dict__)
            except (requests.exceptions.RequestException,
                    urllib3.exceptions.HTTPError):
                logger.debug('Lost connection to camera')
                self._connect()
        else:
            self._connect()

    def _connect(self):
        logger.debug('Try to connect')
        devices = discover_panasonic_camera_devices()
        if devices:
            device = devices[0]
            hostname = urlparse(device.location).hostname
            logger.debug(
                'Connect to {}: {}'.format(device.friendly_name, hostname))
            self.camera = PanasonicCamera(hostname)
            self._ensure_connection()
            self._start_camera_stream()
        else:
            self.camera = None
            logger.debug('No camera found')

    def _start_camera_stream(self):
        try:
            self.camera.recmode()
            self.camera.start_stream()
        except (requests.exceptions.RequestException,
                urllib3.exceptions.HTTPError,
                BusyError) as e:
            logger.error('Could not start camera stream: %s', e)

    def run(self):
        self._ensure_connection()
        super().run()

    def cancel(self):
        if self.camera:
            logger.debug('stop camera stream')
            try:
                self.camera.stop_stream()
            except CriticalError as e:
                logger.warning('Could not stop camera stream: %s', e)
        super().cancel()


def main():
    logging.basicConfig(level=logging.DEBUG)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    daemon = PanasonicCameraManager()
    daemon.start()

    # https://www.g-loaded.eu/2016/11/24/how-to-terminate-running-python-threads-using-signals/
    while True:
        try:
            time.sleep(1)
        except ProgramKilled:
            print("Program killed: running cleanup code")
            daemon.cancel()
            break


if __name__ == "__main__":
    main()
