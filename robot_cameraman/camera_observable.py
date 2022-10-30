import csv
import datetime
import logging
from dataclasses import fields
from pathlib import Path

from panasonic_camera.live_view import ExHeader, ExHeader1, ExHeader2, ExHeader8
from robot_cameraman.events import EventEmitter, Event

logger: logging.Logger = logging.getLogger(__name__)


class PanasonicCameraObservable:

    def __init__(self, min_focal_length: float, event_emitter: EventEmitter):
        super().__init__()
        self.min_focal_length = min_focal_length
        self._event_emitter = event_emitter

    def on_ex_header(self, ex_header: ExHeader):
        if (isinstance(ex_header, ExHeader1)
                or isinstance(ex_header, ExHeader2)):
            zoom_index = ex_header.b
            logger.debug(f"zoom index {zoom_index}")
            self._event_emitter.emit(Event.ZOOM_INDEX, zoom_index)
            # Zoom ratio is encoded as integer,
            # e.g 1.5x is encoded as 15.
            # Convert it to float:
            zoom_ratio = ex_header.zoomRatio / 10
            logger.debug(f"zoom ratio {zoom_ratio}")
            self._event_emitter.emit(Event.ZOOM_RATIO, zoom_ratio)
            focal_length = zoom_ratio * self.min_focal_length
            logger.debug(f"focal length {focal_length}")
            self._event_emitter.emit(Event.FOCAL_LENGTH, focal_length)


class ExHeaderToCsvWriter:
    def __init__(self) -> None:
        root = Path(__file__).parent.parent
        now = datetime.datetime.today()
        prefix = f'ex-header_{now.strftime("%d-%m-%Y_%H%M%S")}'
        self._csv_writer = csv.writer(open(root / f'{prefix}.csv', 'w'))
        self._ex_header_attribute_names = [
            field.name for field in fields(ExHeader8)]
        # self._ex_header_attribute_names = [
        #     'zoomRatio',
        #     'b',
        #     'u',
        #     'A']
        self._csv_writer.writerow(self._ex_header_attribute_names)
        self._previous_row = None

    def on_ex_header(self, ex_header: ExHeader):
        if isinstance(ex_header, ExHeader8):
            row = [getattr(ex_header, attribute_name)
                   for attribute_name in self._ex_header_attribute_names]
            if self._previous_row != row:
                self._previous_row = row
                self._csv_writer.writerow(row)
        else:
            logger.error(f'unexpected header type: {ex_header}')
