from typing import Tuple, Iterable
from typing_extensions import Protocol


class Box(Protocol):
    x: float
    y: float
    width: float
    height: float
    center: Tuple[float, float]
    coordinates: Iterable[float]

    @staticmethod
    def from_coordinates(x1: float, y1: float, x2: float, y2: float):
        return TwoPointsBox(x1, y1, x2, y2)

    @staticmethod
    def from_points_iterable(points: Iterable[Iterable[float]]):
        (x1, y1), (x2, y2) = points
        return TwoPointsBox(x1, y1, x2, y2)

    @staticmethod
    def from_coordinate_iterable(coordinates: Iterable[float]):
        x1, y1, x2, y2 = coordinates
        return TwoPointsBox(x1, y1, x2, y2)


class TwoPointsBox(Box):

    def __init__(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.x = x1
        self.y = y1
        self.width = abs(x2 - x1)
        self.height = abs(y2 - y1)
        self.center = (abs(x1 + x2) / 2, abs(y1 + y2) / 2)
        self.coordinates = [x1, y1, x2, y2]

