import argparse
import curses
import json
import signal
import sys
import threading
import traceback
from pathlib import Path
from time import sleep
from typing import Any, TYPE_CHECKING, Optional, Dict
from typing_extensions import Protocol

from panasonic_camera.camera_manager import PanasonicCameraManager
from panasonic_camera.live_view import ExHeader, ExHeader1
from robot_cameraman.camera_controller import ElapsedTime
from robot_cameraman.camera_observable import PanasonicCameraObservable
from robot_cameraman.live_view import PanasonicLiveView
from robot_cameraman.tools.util.json import DataclassDictJsonEncoder
from robot_cameraman.tools.util.tsv import print_data_class_tsv
from robot_cameraman.zoom import ZoomRatioIndexRangesBuilder, \
    ZoomRatioIndexRange

if TYPE_CHECKING:
    import _curses

    CursesWindow = _curses.window
else:
    CursesWindow = Any


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


class InteractiveZoomIndexAnalyzer:
    _window: CursesWindow
    _camera_manager: PanasonicCameraManager
    _live_view: PanasonicLiveView
    _zoom_ratio: Optional[float] = None
    _zoom_index: Optional[int] = None
    zoom_index_to_ratio: Dict[int, float] = {}

    def __init__(
            self,
            camera_manager: PanasonicCameraManager,
            live_view: PanasonicLiveView) -> None:
        self._camera_manager = camera_manager
        self._live_view = live_view

    def _add_line(self, line: str):
        self._window.addstr(line + '\n')

    def on_ex_header(self, ex_header: ExHeader):
        if isinstance(ex_header, ExHeader1):
            self._zoom_ratio = ex_header.zoomRatio / 10
            self._zoom_index = ex_header.b
            self.zoom_index_to_ratio[self._zoom_index] = self._zoom_ratio

    def _read_zoom(self):
        self._live_view.image()

    def run(self, window: CursesWindow):
        self._window = window
        curses.echo()
        self._connect_to_camera()
        self._live_view.add_ex_header_listener(self.on_ex_header)
        self._wait_for_current_zoom_index()

        user_input = None
        while True:
            self.print_zoom_index_to_ratio()
            self._add_line(
                f'Current index: {self._zoom_index}, ratio: {self._zoom_ratio}\n')
            if user_input is not None:
                self._add_line(f'previous user input: {user_input}\n')

            self._window.addstr('Zoom to index (q to quit): ')
            try:
                curses.flushinp()
                user_input = self._window.getstr(2).decode(encoding="utf-8")
                if user_input.lower() == 'q':
                    return
                target_index = int(user_input)
            except ValueError:
                self._window.clear()
                continue
            if self._zoom_index == target_index:
                continue
            is_zoom_in = self._zoom_index < target_index
            if is_zoom_in:
                self._camera_manager.camera.zoom_in_slow()
            else:
                self._camera_manager.camera.zoom_out_slow()
            while (
                    self._zoom_index < target_index
                    if is_zoom_in else self._zoom_index > target_index
            ):
                self._read_zoom()
                self._window.clear()
                self._add_line(f'Zooming {"in" if is_zoom_in else "out"}'
                               f' to index: {target_index}\n')
                self._add_line(f'Current index: {self._zoom_index},'
                               f' ratio: {self._zoom_ratio}')
                self._add_line(f'\nPress ESC to stop zooming')
                self._window.refresh()
                curses.noecho()
                self._window.nodelay(True)
                if self._window.getch() == 27:
                    target_index = self._zoom_index
                    self._window.nodelay(False)
                    break
                self._window.nodelay(False)
            curses.echo()
            camera_manager.camera.zoom_stop()
            elapsed_time = ElapsedTime()
            while elapsed_time.get() < 1:
                self._read_zoom()
                self._window.clear()
                self._add_line(f'Stopped zoom at index {target_index}')
                self._add_line(f'Waiting for zoom to change again')
                self._add_line(f'Current index: {self._zoom_index},'
                               f' ratio: {self._zoom_ratio}')
                self._window.refresh()
            self._window.clear()
            self._add_line(f'Stopped zoom at index {target_index}\n')

    def print_zoom_index_to_ratio(self, print_line=None):
        if print_line is None:
            print_line = self._add_line
        print_line(f'Known index-ratio relationships:')
        previous_index = None
        for index, ratio in sorted(self.zoom_index_to_ratio.items()):
            if previous_index is not None:
                for skipped_index in range(previous_index + 1, index):
                    print_line(f'  index: {skipped_index:2}, ratio:   ?')
            print_line(f'  index: {index:2}, ratio: {ratio:4.1f}')
            previous_index = index
        print_line('')

    def _wait_for_current_zoom_index(self):
        self._window.addstr(f'wait for current zoom index')
        self._window.refresh()
        while self._zoom_index is None:
            self._read_zoom()
        self._window.clear()

    def _connect_to_camera(self):
        self._camera_manager.start()
        if self._camera_manager.camera is None:
            self._add_line('waiting for camera connection')
            self._window.refresh()
            while self._camera_manager.camera is None:
                sleep(0.1)
                self._window.clear()
                self._window.addstr('waiting for camera connection')
                self._window.refresh()
            self._window.clear()
            self._add_line('successfully connected to camera')
            self._add_line('waiting 3 second for camera to get ready')
            self._window.refresh()
            sleep(3)
            self._window.clear()
        else:
            self._add_line('camera already connected')
            self._window.refresh()


args = parse_arguments()
camera_manager = PanasonicCameraManager(
    identify_as=args.identifyToPanasonicCameraAs)

live_view = PanasonicLiveView(args.ip, args.port)
camera_observable = PanasonicCameraObservable(
    min_focal_length=args.cameraMinFocalLength)
live_view.add_ex_header_listener(camera_observable.on_ex_header)

signal.signal(signal.SIGINT, quit)
signal.signal(signal.SIGTERM, quit)

analyzer = InteractiveZoomIndexAnalyzer(camera_manager=camera_manager,
                                        live_view=live_view)
# noinspection PyBroadException
try:
    curses.wrapper(analyzer.run)
    analyzer.print_zoom_index_to_ratio(print_line=print)
    builder = ZoomRatioIndexRangesBuilder()
    for index, ratio in sorted(analyzer.zoom_index_to_ratio.items()):
        builder.add(zoom_index=index, zoom_ratio=ratio)
    zoom_ratio_index_ranges = list(builder.zoom_ratio_to_range.values())
    print('\n' * 2)
    print_data_class_tsv(
        ZoomRatioIndexRange,
        zoom_ratio_index_ranges,
        {
            'zoom_ratio': '10.1f'
        })
    if args.output is not None:
        args.output.write_text(
            json.dumps(
                zoom_ratio_index_ranges,
                cls=DataclassDictJsonEncoder,
                indent=2))
    camera_manager.camera.zoom_out_fast()
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
