import argparse
import json
import logging
import signal
# noinspection Mypy
import sys
import threading
import traceback
from pathlib import Path
from time import sleep
from typing import List, Optional, Dict

from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from panasonic_camera.live_view import ExHeader, ExHeader1
from robot_cameraman.camera_controller import ElapsedTime
from robot_cameraman.camera_observable import \
    PanasonicCameraObservable
from robot_cameraman.live_view import PanasonicLiveView
from robot_cameraman.tools.util.json import DataclassDictJsonEncoder
from robot_cameraman.zoom import ZoomRatioIndexRange


class Arguments(Protocol):
    ip: str
    port: int
    identifyToPanasonicCameraAs: str
    output: Path
    debug: bool
    cameraMinFocalLength: float
    maxZoomRatio: float


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser(
        description="Analyze zoom steps and speed.")
    parser.add_argument('--ip', type=str,
                        default='0.0.0.0',
                        help="UDP Socket IP address of Panasonic live view.")
    parser.add_argument('--port', type=int,
                        default=49199,
                        help="UDP Socket port of Panasonic live view.")
    parser.add_argument('--identifyToPanasonicCameraAs', type=str,
                        help="When connecting to the camera for remote control,"
                             " identify ourselves with this name. Required on"
                             "certain cameras including DC-FZ80."
                        )
    parser.add_argument('--output',
                        type=Path,
                        default=None,
                        help="JSON output file of analysis results.")
    parser.add_argument('--debug',
                        action='store_true',
                        help="Enable debug logging")
    parser.add_argument('--cameraMinFocalLength',
                        type=float, default=6.0,
                        help="Minimum focal length in millimeter"
                             "of the used camera. The actual focal length"
                             "and not the 35mm equivalent is expected.")
    parser.add_argument('--maxZoomRatio',
                        type=float, default=14.3,
                        help="Maximum zoom ratio of the used camera.")
    # noinspection PyTypeChecker
    return parser.parse_args()


def quit(sig=None, frame=None, exit_code=0):
    global camera_manager
    print("Exiting...")
    if threading.current_thread() != camera_manager:
        print('wait for camera manager thread')
        camera_manager.cancel()
        camera_manager.join()
        exit(exit_code)


def configure_logging():
    # TODO filename or output directory as program argument
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.ERROR,
        filename=f'{args.output}.log' if args.output else None,
        filemode='w',
        format='%(asctime)s %(name)-50s %(levelname)-8s %(message)s')
    console = logging.StreamHandler()
    # TODO level as program argument
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(levelname)-8s %(name)-12s: %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)


args = parse_arguments()
configure_logging()
camera_manager = PanasonicCameraManager(
    identify_as=args.identifyToPanasonicCameraAs)

live_view = PanasonicLiveView(args.ip, args.port)
camera_observable = PanasonicCameraObservable(
    min_focal_length=args.cameraMinFocalLength)
live_view.add_ex_header_listener(camera_observable.on_ex_header)

signal.signal(signal.SIGINT, quit)
signal.signal(signal.SIGTERM, quit)

camera_manager.start()
if camera_manager.camera is None:
    print('waiting for camera connection')
    while camera_manager.camera is None:
        sleep(1)
        print('...')
    print('successfully connected to camera')
    print('waiting 3 second for camera to get ready')
    sleep(3)
else:
    print('camera already connected')
print(f"camera should be ready")

zoom_ratio: Optional[float] = None
zoom_index: Optional[int] = None


def on_ex_header(ex_header: ExHeader):
    global zoom_ratio, zoom_index
    if isinstance(ex_header, ExHeader1):
        zoom_ratio = ex_header.zoomRatio / 10
        zoom_index = ex_header.b


def print_zoom():
    global zoom_ratio, zoom_index
    print(f'ratio: {zoom_ratio:4.1f}, index: {zoom_index:2}')


def read_zoom():
    global live_view
    live_view.image()


def read_zoom_indices():
    global zoom_ratio, zoom_index
    print(f'zoom in')
    camera_manager.camera.zoom_in_slow()
    is_max_zoom_ratio_reached = False
    zoom_index_range_of_zoom_ratio = dict()
    while not is_max_zoom_ratio_reached:
        read_zoom()
        print_zoom()
        if zoom_ratio not in zoom_index_range_of_zoom_ratio:
            zoom_index_range_of_zoom_ratio[zoom_ratio] = \
                ZoomRatioIndexRange(
                    zoom_ratio=zoom_ratio,
                    min_index=zoom_index,
                    max_index=zoom_index)
        else:
            zoom_index_range_of_zoom_ratio[zoom_ratio].max_index = zoom_index
        # TODO replace magic number 48 with CLI argument
        #  or determine/estimate it
        is_max_zoom_ratio_reached = zoom_index == 48
    return zoom_index_range_of_zoom_ratio


def zoom_out():
    if zoom_index != 0:
        print(f'zoom out to index 0')
        camera_manager.camera.zoom_out_fast()
        while zoom_index != 0:
            read_zoom()
            print_zoom()


def stop_zoom_when_index_is_reached(index: int, is_zoom_in: bool):
    global zoom_ratio, zoom_index
    print(f'waiting for zoom index {index} to be reached')
    while zoom_index < index if is_zoom_in else zoom_index > index:
        read_zoom()
        print_zoom()
    print(f'stop zoom at index {index}')
    camera_manager.camera.zoom_stop()


# noinspection PyShadowingNames
def measure_stops(indices: List[ZoomRatioIndexRange]) -> Dict[int, int]:
    global zoom_ratio, zoom_index
    min_index = indices[0].min_index
    max_index = indices[-1].max_index
    measurements: Dict[int, int] = {}
    for i in range(min_index, max_index):
        zoom_out()
        sleep(1)
        camera_manager.camera.zoom_in_slow()
        stop_zoom_when_index_is_reached(i, is_zoom_in=True)
        if i != zoom_index:
            print(f'failed to stop zoom when index {i} is reached,'
                  f' since zoom index got skipped',
                  file=sys.stderr)
            continue
        print(f'wait for zoom index to change again')
        elapsed_time = ElapsedTime()
        while elapsed_time.get() < 1:
            read_zoom()
            print_zoom()
        print(f'stopping zoom when index {i} was reached,'
              f' resulted in zoom index {zoom_index}')
        measurements[i] = zoom_index
    return measurements


# noinspection PyBroadException
try:
    live_view.add_ex_header_listener(on_ex_header)
    print(f'wait for current zoom index')
    while zoom_index is None:
        read_zoom()
    print_zoom()
    zoom_out()
    print(f'start analysis')
    # @formatter:off
    # indices = {1.0: ZoomRatioIndexRange(zoom_ratio=1.0, min_index=0, max_index=5), 2.0: ZoomRatioIndexRange(zoom_ratio=2.0, min_index=6, max_index=11), 3.0: ZoomRatioIndexRange(zoom_ratio=3.0, min_index=12, max_index=17), 4.0: ZoomRatioIndexRange(zoom_ratio=4.0, min_index=18, max_index=22), 5.0: ZoomRatioIndexRange(zoom_ratio=5.0, min_index=24, max_index=28), 6.0: ZoomRatioIndexRange(zoom_ratio=6.0, min_index=30, max_index=33), 7.1: ZoomRatioIndexRange(zoom_ratio=7.1, min_index=36, max_index=36), 8.0: ZoomRatioIndexRange(zoom_ratio=8.0, min_index=37, max_index=39), 10.0: ZoomRatioIndexRange(zoom_ratio=10.0, min_index=40, max_index=41), 11.0: ZoomRatioIndexRange(zoom_ratio=11.0, min_index=42, max_index=43), 12.0: ZoomRatioIndexRange(zoom_ratio=12.0, min_index=44, max_index=45), 13.0: ZoomRatioIndexRange(zoom_ratio=13.0, min_index=46, max_index=47), 14.3: ZoomRatioIndexRange(zoom_ratio=14.3, min_index=48, max_index=48)}
    # stops = {0:  0, 1:  1, 2:  2, 3:  3, 4:  5, 5:  5, 6:  7, 7:  7, 8: 10, 9: 10, 10: 11, 11: 13, 12: 14, 13: 14, 14: 17, 15: 18, 17: 19, 19: 22, 21: 24, 26: 28, 30: 36, 33: 36, 36: 36, 37: 38, 38: 39, 39: 39, 41: 41, 42: 42, 44: 45, 45: 46, 46: 47, 47: 48 }
    # @formatter:on
    indices = read_zoom_indices()
    print(f'indices: {indices}')
    stops = measure_stops(list(indices.values()))
    print(f'stops: {stops}')
    for i, s in stops.items():
        print(f'stop-when-reached: {i:2} stops-at: {s:2}')
    if args.output is not None:
        args.output.write_text(
            json.dumps(
                list(indices.values()),
                cls=DataclassDictJsonEncoder,
                indent=2))
except Exception:
    # noinspection PyBroadException
    try:
        print(f'\n\ntry to zoom out camera (completely)')
        camera_manager.camera.zoom_out_fast()
    except Exception:
        print(f'failed to zoom out camera: {traceback.format_exc()}',
              file=sys.stderr)
    print(f'analysis failed: {traceback.format_exc()}',
          file=sys.stderr)
    quit(1)
quit()
