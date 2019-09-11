from dataclasses import dataclass
from typing import Iterable

from typing_extensions import Protocol


@dataclass
class Point:
    x: float
    y: float

    def set(self, x: float, y: float):
        self.x = x
        self.y = y

    def __iter__(self):
        yield self.x
        yield self.y


class Box(Protocol):
    x: float
    y: float
    width: float
    height: float
    center: Point
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

    @staticmethod
    def from_center_and_size(center: Point, width: float, height: float):
        return CenterSizeBox(center, width, height)


class TwoPointsBox(Box):

    def __init__(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.x = x1
        self.y = y1
        self.width = abs(x2 - x1)
        self.height = abs(y2 - y1)
        self.center = Point(abs(x1 + x2) / 2, abs(y1 + y2) / 2)
        self.coordinates = [x1, y1, x2, y2]


class CenterSizeBox(Box):

    def __init__(self, center: Point, width: float, height: float) -> None:
        half_width = width / 2
        half_height = height / 2
        x1 = center.x - half_width
        x2 = center.x + half_width
        y1 = center.y - half_height
        y2 = center.y + half_height
        self.x = x1
        self.y = y1
        self.width = width
        self.height = height
        self.center = center
        self.coordinates = [x1, y1, x2, y2]
