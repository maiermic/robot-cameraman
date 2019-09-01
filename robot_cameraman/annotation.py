from typing import Optional, Dict, Iterable, Tuple, NamedTuple

import PIL.Image
import PIL.ImageDraw
from PIL.ImageDraw import ImageDraw
from PIL.ImageFont import FreeTypeFont
from edgetpu.detection.engine import DetectionCandidate

from robot_cameraman.box import Box, Point
from robot_cameraman.tracking import Destination


class Target(NamedTuple):
    box: Box
    detection_candidate: DetectionCandidate


class ImageAnnotator:
    target: Optional[Target] = None

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
            inference_results: Iterable[DetectionCandidate]) -> None:
        draw = PIL.ImageDraw.Draw(image)
        # Iterate through result list. Note that results are already sorted by
        # confidence score (highest to lowest) and records with a lower score
        # than the threshold are already removed.
        target_box_found = False
        for idx, obj in enumerate(inference_results):
            box = obj.bounding_box
            if obj.label_id != self.target_label_id:
                color = (255, 255, 255)
            else:
                color = (0, 255, 0)
                if not target_box_found:
                    target_box_found = True
                    self.target = Target(box, obj)
            self.draw_annotated_box(draw, box, obj, color)
        if self.target is None or target_box_found:
            return
        self.draw_annotated_box(draw, self.target.box,
                                self.target.detection_candidate,
                                (255, 0, 0))

    def draw_annotated_box(
            self,
            draw: ImageDraw,
            box: Box,
            obj: DetectionCandidate,
            color: Tuple[int, int, int]) -> None:
        draw.rectangle(box.coordinates, outline=color)
        draw_point(draw, box.center, color)
        # Annotate image with label and confidence score
        display_str = self.labels[obj.label_id] + ": " + str(
            round(obj.score * 100, 2)) + "%"
        draw.text((box.x, box.y), display_str, font=self.font)


def draw_destination(
        image: PIL.Image.Image,
        destination: Destination,
        color: Tuple[int, int, int] = (255, 0, 255)) -> None:
    draw = PIL.ImageDraw.Draw(image)
    draw_point(draw, destination.center, color)
    draw.rectangle(destination.box, outline=color)


def draw_point(
        draw: ImageDraw,
        point: Point,
        color: Tuple[int, int, int],
        radius: int = 3) -> None:
    x, y = point
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
