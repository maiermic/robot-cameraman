import logging
from abc import ABC
from enum import Enum, auto
from typing import List, Callable, Dict

from panasonic_camera.live_view import ExHeader, ExHeader1, ExHeader2

logger: logging.Logger = logging.getLogger(__name__)


class ObservableCameraProperty(Enum):
    FOCAL_LENGTH = auto()
    ZOOM_RATIO = auto()


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
