import logging
from logging import Logger
from typing import Iterable

import PIL.Image
from PIL import ImageDraw

from robot_cameraman.annotation import draw_point
from robot_cameraman.box import Point
from robot_cameraman.pose_detection.pose import Pose

logger: Logger = logging.getLogger(__name__)


class PoseDraw:
    keypoint_radius = 3
    _key_point_center: Point

    def __init__(self) -> None:
        self._key_point_center = Point(x=0, y=0)

    def draw(self, image: PIL.Image.Image, poses: Iterable[Pose]):
        draw = ImageDraw.Draw(image)
        for pose in poses:
            logger.debug(f'draw pose: {pose}')
            self.draw_edges(draw, pose)
            self.draw_key_points(draw, pose)
            # bounding_box = pose.get_bounding_box()
            # draw.rectangle(bounding_box.coordinates(),
            #                outline=(255, 0, 0))

    def draw_edges(self, draw, pose):
        for a, b in pose.edges():
            draw.line(xy=((a.x, a.y), (b.x, b.y)),
                      width=3,
                      fill=(255, 255, 0))

    def draw_key_points(self, draw: ImageDraw, pose: Pose):
        for kp in pose:
            self._key_point_center.set(x=kp.x, y=kp.y)
            draw_point(draw,
                       self._key_point_center,
                       color=(0, 255, 0),
                       radius=self.keypoint_radius)
