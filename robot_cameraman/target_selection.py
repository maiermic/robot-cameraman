import logging
from logging import Logger
from typing import Dict, Optional, NamedTuple, List

from PIL.Image import Image
from more_itertools import first_true
from typing_extensions import Protocol

from robot_cameraman.box import Point
from robot_cameraman.image_detection import DetectionCandidate
from robot_cameraman.pose_detection.detection import PoseDetectionEngine
from robot_cameraman.pose_detection.draw import PoseDraw
from robot_cameraman.pose_detection.pose import Pose, KeyPoint

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


class PoseMatcher(Protocol):
    def is_matching_pose(self, pose: Pose) -> bool:
        raise NotImplementedError


class HandsUpPoseMatcher(PoseMatcher):
    confidence: float = 0.4

    def is_matching_pose(self, pose: Pose) -> bool:
        face = self.keep_key_points_with_minimum_confidence(
            pose.nose,
            pose.left_eye,
            pose.right_eye,
            pose.left_ear,
            pose.right_ear,
        )
        shoulders = self.keep_key_points_with_minimum_confidence(
            pose.left_shoulder,
            pose.right_shoulder,
        )
        elbows = self.keep_key_points_with_minimum_confidence(
            pose.left_elbow,
            pose.right_elbow,
        )
        wrists = self.keep_key_points_with_minimum_confidence(
            pose.left_wrist,
            pose.right_wrist,
        )
        arms = elbows + wrists
        if len(arms) >= 2 and len(shoulders) >= 4:
            return self.are_hands_higher_than_body(hands=arms, body=shoulders)
        else:
            logger.error(
                f'too low confidence in key points of arms or shoulders,'
                f'high enough key points count:'
                f' arms={len(arms)}, shoulders={len(shoulders)}'
            )
        if len(wrists) >= 2 and len(face) >= 4:
            return self.are_hands_higher_than_body(hands=wrists, body=face)
        else:
            logger.error(
                f'too low confidence in key points of wrists or face,'
                f'high enough key points count:'
                f' wrists={len(wrists)}, face={len(face)}'
            )
        return False

    def keep_key_points_with_minimum_confidence(
            self, *key_points: KeyPoint) -> List[KeyPoint]:
        return list(filter(lambda kp: kp.confidence > self.confidence,
                           key_points))

    @staticmethod
    def are_hands_higher_than_body(
            hands: List[KeyPoint], body: List[KeyPoint]) -> bool:
        def are_hands_higher(key_point: KeyPoint):
            # higher in the image means smaller y,
            # since origin is at the top left corner of the image
            # and y increases to the bottom
            return all(map(lambda h: h.y < key_point.y,
                           hands))

        logger.debug(f"body y's: {', '.join(f'{kp.y:6.2f}' for kp in body)}")
        logger.debug(f"hands y's: {', '.join(f'{kp.y:6.2f}' for kp in hands)}")

        return all(map(are_hands_higher, body))


class PoseSelectTargetStrategy(SelectTargetStrategy):
    coordinate: Optional[Point] = None
    poses: Optional[List[Pose]]
    _image: Optional[Image]

    def __init__(
            self,
            pose_detection_engine: PoseDetectionEngine,
            pose_matcher: PoseMatcher) -> None:
        self.poses = None
        self._pose_detection_engine = pose_detection_engine
        self._pose_matcher = pose_matcher

    def update_live_view_image(self, image: Image):
        self._image = image
        self.poses = None

    def select(
            self,
            candidates: Dict[int, DetectionCandidate]
    ) -> Optional[Target]:
        self.poses = list(self._pose_detection_engine.detect(self._image))
        logger.debug(f'poses detected: {self.poses}')
        pose = self._find_matching_pose()
        if not pose:
            return None
        logger.debug(f'pose matched: {pose}')
        pose_bounding_box = pose.get_bounding_box()
        target = None
        max_intersection_area = 0
        for target_id, candidate in candidates.items():
            intersection_area = pose_bounding_box.percental_intersection_area(
                candidate.bounding_box)
            if intersection_area > max_intersection_area:
                max_intersection_area = intersection_area
                target = Target(target_id, candidate)
        return target

    def _find_matching_pose(self) -> Optional[Pose]:
        return first_true(self.poses,
                          None,
                          self._pose_matcher.is_matching_pose)


class PoseSelectTargetStrategyImageAnnotator:
    def __init__(
            self,
            pose_select_target_strategy: PoseSelectTargetStrategy,
            pose_draw: PoseDraw) -> None:
        self._pose_select_target_strategy = pose_select_target_strategy
        self._pose_draw = pose_draw

    def annotate(self, image: Image):
        if self._pose_select_target_strategy.poses:
            self._pose_draw.draw(image, self._pose_select_target_strategy.poses)
