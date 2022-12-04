import enum
from typing import NamedTuple, Iterable

from robot_cameraman.box import Box

NUM_KEY_POINTS = 17


class KeyPointType(enum.IntEnum):
    """Pose key points."""
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16


EDGES = (
    (KeyPointType.NOSE, KeyPointType.LEFT_EYE),
    (KeyPointType.NOSE, KeyPointType.RIGHT_EYE),
    (KeyPointType.NOSE, KeyPointType.LEFT_EAR),
    (KeyPointType.NOSE, KeyPointType.RIGHT_EAR),
    (KeyPointType.LEFT_EAR, KeyPointType.LEFT_EYE),
    (KeyPointType.RIGHT_EAR, KeyPointType.RIGHT_EYE),
    (KeyPointType.LEFT_EYE, KeyPointType.RIGHT_EYE),
    (KeyPointType.LEFT_SHOULDER, KeyPointType.RIGHT_SHOULDER),
    (KeyPointType.LEFT_SHOULDER, KeyPointType.LEFT_ELBOW),
    (KeyPointType.LEFT_SHOULDER, KeyPointType.LEFT_HIP),
    (KeyPointType.RIGHT_SHOULDER, KeyPointType.RIGHT_ELBOW),
    (KeyPointType.RIGHT_SHOULDER, KeyPointType.RIGHT_HIP),
    (KeyPointType.LEFT_ELBOW, KeyPointType.LEFT_WRIST),
    (KeyPointType.RIGHT_ELBOW, KeyPointType.RIGHT_WRIST),
    (KeyPointType.LEFT_HIP, KeyPointType.RIGHT_HIP),
    (KeyPointType.LEFT_HIP, KeyPointType.LEFT_KNEE),
    (KeyPointType.RIGHT_HIP, KeyPointType.RIGHT_KNEE),
    (KeyPointType.LEFT_KNEE, KeyPointType.LEFT_ANKLE),
    (KeyPointType.RIGHT_KNEE, KeyPointType.RIGHT_ANKLE),
)


class KeyPoint(NamedTuple):
    y: float
    x: float
    confidence: float


class Pose(NamedTuple):
    nose: KeyPoint
    left_eye: KeyPoint
    right_eye: KeyPoint
    left_ear: KeyPoint
    right_ear: KeyPoint
    left_shoulder: KeyPoint
    right_shoulder: KeyPoint
    left_elbow: KeyPoint
    right_elbow: KeyPoint
    left_wrist: KeyPoint
    right_wrist: KeyPoint
    left_hip: KeyPoint
    right_hip: KeyPoint
    left_knee: KeyPoint
    right_knee: KeyPoint
    left_ankle: KeyPoint
    right_ankle: KeyPoint

    def edges(self) -> Iterable[tuple[KeyPoint, KeyPoint]]:
        for a, b in EDGES:
            yield self[a], self[b]

    def get_bounding_box(self) -> Box:
        min_x, min_y, max_x, max_y = None, None, None, None
        key_point: KeyPoint
        for key_point in self:
            if min_x is None or min_x > key_point.x:
                min_x = key_point.x
            if min_y is None or min_y > key_point.y:
                min_y = key_point.y
            if max_x is None or max_x < key_point.x:
                max_x = key_point.x
            if max_y is None or max_y < key_point.y:
                max_y = key_point.y
        return Box.from_coordinates(min_x, min_y, max_x, max_y)
