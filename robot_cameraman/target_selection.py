import logging
from logging import Logger
from typing import Dict, Optional, NamedTuple

from typing_extensions import Protocol

from robot_cameraman.box import Point
from robot_cameraman.image_detection import DetectionCandidate

logger: Logger = logging.getLogger(__name__)


class Target(NamedTuple):
    id: int
    candidate: DetectionCandidate


class SelectTargetStrategy(Protocol):
    def select(
            self,
            candidates: Dict[int, DetectionCandidate]
    ) -> Optional[Target]:
        pass


class SelectFirstTargetStrategy(SelectTargetStrategy):
    def select(
            self,
            candidates: Dict[int, DetectionCandidate]
    ) -> Optional[Target]:
        ts = candidates.items()
        if ts:
            # noinspection PyTypeChecker
            return Target._make(next(iter(ts)))
        return None


class SelectTargetAtCoordinateStrategy(SelectTargetStrategy):
    coordinate: Optional[Point] = None

    def select(
            self,
            candidates: Dict[int, DetectionCandidate]
    ) -> Optional[Target]:
        if self.coordinate is None:
            return None
        for id, candidate in candidates.items():
            if candidate.bounding_box.contains_point(self.coordinate):
                logger.debug(f'select target at coordinate {self.coordinate}')
                self.coordinate = None
                return Target(id=id, candidate=candidate)
        self.coordinate = None
        return None
