from pathlib import Path
from typing import List

import PIL.Image
import PIL.ImageFont
import edgetpu.detection.engine

DetectionCandidate = edgetpu.detection.engine.DetectionCandidate


class DetectionEngine:
    def __init__(
            self,
            model: Path,
            confidence: float,
            max_objects: int) -> None:
        self._engine = edgetpu.detection.engine.DetectionEngine(str(model))
        self._confidence = confidence
        self._max_objects = max_objects

    def detect(self, image: PIL.Image.Image) -> List[DetectionCandidate]:
        return self._engine.DetectWithImage(
            image,
            threshold=self._confidence,
            keep_aspect_ratio=True,
            relative_coord=False,
            top_k=self._max_objects)
