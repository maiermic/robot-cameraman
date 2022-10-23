import csv
import datetime
import logging
from abc import ABC
from dataclasses import fields
from enum import Enum, auto
from pathlib import Path
from typing import List, Callable, Dict

from panasonic_camera.live_view import ExHeader, ExHeader1, ExHeader2, ExHeader8

logger: logging.Logger = logging.getLogger(__name__)


class ObservableCameraProperty(Enum):
    FOCAL_LENGTH = auto()
    ZOOM_RATIO = auto()
    ZOOM_INDEX = auto()


CameraObservableListener = Callable


class CameraObservable(ABC):
    _listeners: Dict[ObservableCameraProperty, List[CameraObservableListener]]

    def __init__(self) -> None:
        self._listeners = dict()

    def add_listener(
            self,
            observable_property: ObservableCameraProperty,
            listener: CameraObservableListener):
        property_listeners = self._get_property_listeners(observable_property)
        property_listeners.append(listener)

    def _get_property_listeners(self, observable_property):
        return self._listeners.setdefault(observable_property, [])

    def _notify_listeners(
            self,
            observable_property: ObservableCameraProperty,
            value):
        property_listeners = self._get_property_listeners(observable_property)
        for listener in property_listeners:
            listener(value)


class PanasonicCameraObservable(CameraObservable):

    def __init__(self, min_focal_length: float):
        super().__init__()
        self.min_focal_length = min_focal_length

    def on_ex_header(self, ex_header: ExHeader):
        if (isinstance(ex_header, ExHeader1)
                or isinstance(ex_header, ExHeader2)):
            zoom_index = ex_header.b
            logger.debug(f"zoom index {zoom_index}")
            self._notify_listeners(
                ObservableCameraProperty.ZOOM_INDEX, zoom_index)
            # Zoom ratio is encoded as integer,
            # e.g 1.5x is encoded as 15.
            # Convert it to float:
            zoom_ratio = ex_header.zoomRatio / 10
            logger.debug(f"zoom ratio {zoom_ratio}")
            self._notify_listeners(
                ObservableCameraProperty.ZOOM_RATIO, zoom_ratio)
            focal_length = zoom_ratio * self.min_focal_length
            logger.debug(f"focal length {focal_length}")
            self._notify_listeners(
                ObservableCameraProperty.FOCAL_LENGTH, focal_length)


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
