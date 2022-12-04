from typing import Optional, Dict, NamedTuple, Callable

import PIL.Image
import PIL.ImageDraw
from PIL.ImageDraw import ImageDraw
from PIL.ImageFont import FreeTypeFont

from robot_cameraman.box import Point
from robot_cameraman.color import Color
from robot_cameraman.image_detection import DetectionCandidate
from robot_cameraman.tracking import Destination


class _Target(NamedTuple):
    id: int
    candidate: DetectionCandidate


class ImageAnnotator:
    _target: Optional[_Target] = None

    def __init__(
            self,
            target_label_id: int,
            labels: Dict[int, str],
            font: FreeTypeFont) -> None:
        self.target_label_id = target_label_id
        self.labels = labels
        self.font = font

    def annotate(
            self,
            image: PIL.Image.Image,
            target_id: Optional[int],
            candidates: Dict[int, DetectionCandidate],
            mode_name: str) -> None:
        draw = PIL.ImageDraw.Draw(image)
        draw.text((0, 0), mode_name, font=self.font)
        # Iterate through result list. Note that results are already sorted by
        # confidence score (highest to lowest) and records with a lower score
        # than the threshold are already removed.
        target_found = False
        for candidate_id, candidate in candidates.items():
            color = (255, 255, 255)
            if candidate_id == target_id:
                color = (0, 255, 0)
                target_found = True
                self._target = _Target(target_id, candidate)
            self.draw_detection_candidate(draw, candidate_id, candidate, color)
        if self._target is None or target_found:
            return
        self.draw_detection_candidate(draw, self._target.id,
                                      self._target.candidate,
                                      (255, 0, 0))

    def draw_detection_candidate(
            self,
            draw: ImageDraw,
            candidate_id: int,
            obj: DetectionCandidate,
            color: Color,
            outline_width: int = 1,
            is_draw_label: bool = True,
            is_draw_candidate_id: bool = True) -> None:
        box = obj.bounding_box
        draw.rectangle(box.coordinates(), outline=color, width=outline_width)
        draw_point(draw, box.center, color)
        if is_draw_label:
            # Annotate image with label and confidence score
            display_str = self.labels[obj.label_id] + ": " + str(
                round(obj.score * 100, 2)) + "%"
            draw.text((box.x, box.y), display_str, font=self.font)
        if is_draw_candidate_id:
            self.draw_candidate_id(draw, box, str(candidate_id))

    def draw_candidate_id(self, draw: ImageDraw, center, candidate_id: str):
        draw.text((center.center.x, center.center.y), candidate_id,
                  font=self.font)


def draw_destination(
        image: PIL.Image.Image,
        destination: Destination,
        color: Color = (255, 0, 255)) -> None:
    draw = PIL.ImageDraw.Draw(image)
    draw_point(draw, destination.center, color)
    draw.rectangle(destination.box.coordinates(), outline=color)
    draw.rectangle(destination.min_size_box.coordinates(),
                   outline=(204, 0, 255))
    draw.rectangle(destination.max_size_box.coordinates(),
                   outline=(204, 0, 255))


def draw_point(
        draw: ImageDraw,
        point: Point,
        color: Color,
        radius: int = 3) -> None:
    x, y = point
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


AnnotateImage = Callable[[PIL.Image.Image], None]
