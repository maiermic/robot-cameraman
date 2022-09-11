from dataclasses import dataclass
from typing import Optional


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
