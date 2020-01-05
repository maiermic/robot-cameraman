from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

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

    def coordinates(self) -> List[float]:
        return [self.x, self.y, self.x + self.width, self.y + self.height]

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

    def contains_point(self, point: Point):
        x, y = point
        return (self.x <= x <= self.x + self.width
                and self.y <= y <= self.y + self.height)

    def area(self):
        return self.width * self.height

    def intersect(self, other: Box) -> Box:
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x + self.width, other.x + other.width)
        y2 = min(self.y + self.height, other.y + other.height)
        if x1 > x2 or y1 > y2:
            # no intersection
            return Box.from_coordinates(x1, y1, x1, y1)
        return Box.from_coordinates(x1, y1, x2, y2)

    def percental_intersection_area(self, other: Box):
        return self.intersect(other).area() / min(self.area(), other.area())


class TwoPointsBox(Box):

    def __init__(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.x = x1
        self.y = y1
        self.width = abs(x2 - x1)
        self.height = abs(y2 - y1)
        self.center = Point(abs(x1 + x2) / 2, abs(y1 + y2) / 2)


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
