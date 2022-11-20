from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import PIL.Image
import PIL.ImageFont
from typing_extensions import Protocol

from robot_cameraman.box import Box


@dataclass
class DetectionCandidate:
    label_id: int
    score: float
    bounding_box: Box


class DetectionEngine(Protocol):
    @abstractmethod
    def detect(self, image) -> Iterable[DetectionCandidate]:
        raise NotImplementedError


class EdgeTpuDetectionEngine(DetectionEngine):
    def __init__(
            self,
            model: Path,
            confidence: float,
            max_objects: int) -> None:
        import pycoral.utils.dataset
        import pycoral.utils.edgetpu
        self._interpreter = pycoral.utils.edgetpu.make_interpreter(str(model))
        self._interpreter.allocate_tensors()
        self._confidence = confidence
        self._max_objects = max_objects

    def detect(self, image: PIL.Image.Image) -> Iterable[DetectionCandidate]:
        from pycoral.adapters import common
        from pycoral.adapters import detect
        import pycoral.utils.dataset
        _, scale = pycoral.adapters.common.set_resized_input(
            self._interpreter,
            image.size,
            lambda size: image.resize(size, PIL.Image.ANTIALIAS))
        self._interpreter.invoke()
        objs = detect.get_objects(
            interpreter=self._interpreter,
            score_threshold=self._confidence,
            image_scale=scale)
        return [
            DetectionCandidate(
                label_id=o.id,
                score=o.score,
                bounding_box=Box.from_coordinate_iterable(o.bbox))
            for o in objs
        ]


class DummyDetectionEngine(DetectionEngine):
    def detect(self, image) -> Iterable[DetectionCandidate]:
        return []
