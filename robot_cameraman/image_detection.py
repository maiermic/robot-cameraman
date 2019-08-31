from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import PIL.Image
import PIL.ImageFont
import edgetpu.detection.engine

from robot_cameraman.box import Box


@dataclass
class DetectionCandidate:
    label_id: int
    score: float
    bounding_box: Box


class DetectionEngine:
    def __init__(
            self,
            model: Path,
            confidence: float,
            max_objects: int) -> None:
        self._engine = edgetpu.detection.engine.DetectionEngine(str(model))
        self._confidence = confidence
        self._max_objects = max_objects

    def detect(self, image: PIL.Image.Image) -> Iterable[DetectionCandidate]:
        return map(
            lambda dc: DetectionCandidate(dc.label_id, dc.score,
                                          Box.from_points_iterable(
                                              dc.bounding_box)),
            self._engine.DetectWithImage(
                image,
                threshold=self._confidence,
                keep_aspect_ratio=True,
                relative_coord=False,
                top_k=self._max_objects))
