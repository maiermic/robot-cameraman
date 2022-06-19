import argparse
import logging
import signal
from logging import Logger
from typing import Optional
from urllib.parse import urlparse

import requests
import time
import urllib3

from panasonic_camera.camera import PanasonicCamera, BusyError, CriticalError
from panasonic_camera.discover import discover_panasonic_camera_devices
from panasonic_camera.interval import signal_handler, IntervalThread, \
    ProgramKilled

logger: Logger = logging.getLogger(__name__)


class PanasonicCameraManager(IntervalThread):
    camera: Optional[PanasonicCamera]
    _identify_as: Optional[str]

    def __init__(self, interval=10, *_args, **_kwargs) -> None:
        super().__init__(interval, self._ensure_connection, *_args, **_kwargs)
        self.camera = None
        self._identify_as = _kwargs.get('identify_as')
        self.is_stream_started = False

    def _ensure_connection(self):
        if self.camera:
            try:
                logger.debug(self.camera.get_state().__dict__)
                if not self.is_stream_started:
                    self._start_camera_stream()
            except (requests.exceptions.RequestException,
                    urllib3.exceptions.HTTPError):
                logger.debug('Lost connection to camera')
                self.is_stream_started = False
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
            # If we have a _identify_as property, assume this is a camera like
            # Panasonic DC-FZ80 which requires registering the remote control
            # device (in this case, us) with the camera first.
            if self._identify_as:
                logger.debug(f'Attempting to identify as {self._identify_as}')
                self.camera.register_with_camera(identify_as=self._identify_as)
            # Some cameras like the Panasonic HC-V380 require to get info
            # capability before starting the camera stream
            self.camera.get_info_capability()
            self._ensure_connection()
        else:
            self.camera = None
            logger.debug('No camera found')

    def _start_camera_stream(self):
        try:
            self.camera.recmode()
            self.camera.start_stream()
            self.is_stream_started = True
            logger.debug('camera stream is started')
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--identifyToCameraAs', type=str,
        help="When connecting to the camera for remote control,"
             " identify ourselves with this name. Required on"
             "certain cameras including DC-FZ80."
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    daemon = PanasonicCameraManager(identify_as=args.identifyToCameraAs)
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
