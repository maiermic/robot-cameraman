import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

import more_itertools


@dataclass()
class ZoomStep:
    zoom_ratio: float
    zoom_in_time: float
    total_zoom_in_time: Optional[float]
    stop_zoom_in_time: Optional[float]
    min_stop_zoom_in_time: Optional[float]
    max_stop_zoom_in_time: Optional[float]
    zoom_out_time: Optional[float]

    def __init__(
            self,
            zoom_ratio: float,
            zoom_in_time: float,
            total_zoom_in_time: Optional[float] = None,
            stop_zoom_in_time: Optional[float] = None,
            min_stop_zoom_in_time: Optional[float] = None,
            max_stop_zoom_in_time: Optional[float] = None,
            zoom_out_time: Optional[float] = None) -> None:
        self.zoom_ratio = zoom_ratio
        self.zoom_in_time = zoom_in_time
        self.total_zoom_in_time = total_zoom_in_time
        self.stop_zoom_in_time = stop_zoom_in_time
        self.min_stop_zoom_in_time = min_stop_zoom_in_time
        self.max_stop_zoom_in_time = max_stop_zoom_in_time
        self.zoom_out_time = zoom_out_time


@dataclass()
class ZoomSteps:
    _zoom_steps: List[ZoomStep]

    def __init__(self, zoom_steps: List[ZoomStep]) -> None:
        self._zoom_steps = zoom_steps

    def get_by_zoom_ratio(self, zoom_ratio: float):
        def has_zoom_ratio(zoom_step: ZoomStep):
            return zoom_step.zoom_ratio == zoom_ratio

        return more_itertools.first_true(
            self._zoom_steps, None, has_zoom_ratio)

    def get_next_greater(self, zoom_step: ZoomStep):
        try:
            i = self._zoom_steps.index(zoom_step)
            return self._zoom_steps[i + 1]
        except (ValueError, IndexError):
            return None


def parse_zoom_steps(file: Path) -> ZoomSteps:
    with open(file) as file_descriptor:
        config = json.load(file_descriptor)
    return ZoomSteps(zoom_steps=[
        ZoomStep(zoom_ratio=data['zoom_ratio'],
                 zoom_in_time=data['zoom_in_time'],
                 total_zoom_in_time=data['total_zoom_in_time'],
                 stop_zoom_in_time=data['stop_zoom_in_time'],
                 min_stop_zoom_in_time=data['min_stop_zoom_in_time'],
                 max_stop_zoom_in_time=data['max_stop_zoom_in_time'],
                 zoom_out_time=data['zoom_out_time'])
        for data in config['slow']])
