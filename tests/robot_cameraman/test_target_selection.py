from unittest.mock import Mock

import pytest

from robot_cameraman.box import Box
from robot_cameraman.image_detection import DetectionCandidate
from robot_cameraman.pose_detection.pose import Pose, KeyPoint
from robot_cameraman.target_selection import SelectFirstTargetStrategy, \
    Target, SelectTargetAtCoordinateStrategy, HandsUpPoseMatcher


class TestSelectFirstTargetStrategy:
    @pytest.fixture()
    def select_target_strategy(self):
        return SelectFirstTargetStrategy()

    def test_select_none(self, select_target_strategy):
        assert select_target_strategy.select({}) is None

    def test_select_first(self, select_target_strategy):
        first = Mock()
        second = Mock()
        selected_target = select_target_strategy.select({1: first, 2: second})
        assert selected_target == Target(id=1, candidate=first)


class TestSelectTargetAtCoordinateStrategy:
    @pytest.fixture()
    def select_target_strategy(self):
        return SelectTargetAtCoordinateStrategy()

    @staticmethod
    def create_candidate_from_coordinates(
            x1: float, y1: float, x2: float, y2: float):
        return DetectionCandidate(
            label_id=1,
            score=1,
            bounding_box=Box.from_coordinates(x1, y1, x2, y2))

    def test_select_none_from_empty_candidates(self, select_target_strategy):
        assert select_target_strategy.select({}) is None

    def test_reset_coordinate_if_no_target_found_at_coordinate(
            self, select_target_strategy):
        select_target_strategy.coordinate = (5, 10)
        candidates = {
            1: self.create_candidate_from_coordinates(20, 20, 25, 25)
        }
        assert select_target_strategy.select(candidates) is None
        assert select_target_strategy.coordinate is None

    def test_select_target_at_coordinate(self, select_target_strategy):
        first = self.create_candidate_from_coordinates(20, 20, 25, 25)
        second = self.create_candidate_from_coordinates(120, 120, 125, 125)

        select_target_strategy.coordinate = (21, 21)
        selected_target = select_target_strategy.select({1: first, 2: second})
        assert selected_target == Target(id=1, candidate=first)
        assert select_target_strategy.coordinate is None

        select_target_strategy.coordinate = (121, 121)
        selected_target = select_target_strategy.select({1: first, 2: second})
        assert selected_target == Target(id=2, candidate=second)
        assert select_target_strategy.coordinate is None


class TestHandsUpPoseMatcher:
    @pytest.fixture()
    def pose_matcher(self):
        return HandsUpPoseMatcher()

    @pytest.fixture()
    def low_confidence(self):
        return 0.1

    @pytest.fixture()
    def high_confidence(self):
        return 0.9

    def create_key_point(
            self,
            x: float = 0,
            y: float = 0,
            confidence: float = 1) -> KeyPoint:
        return KeyPoint(x=x, y=y, confidence=confidence)

    def test_are_hands_higher_than_body(self, pose_matcher):
        assert pose_matcher.are_hands_higher_than_body(
            hands=[
                self.create_key_point(y=30.07),
                self.create_key_point(y=28.11),
            ],
            body=[
                self.create_key_point(y=224.17),
                self.create_key_point(y=218.28),
                self.create_key_point(y=230.07),
                self.create_key_point(y=232.04),
            ])
        assert not pose_matcher.are_hands_higher_than_body(
            hands=[
                self.create_key_point(y=30.07),
                self.create_key_point(y=328.11),
            ],
            body=[
                self.create_key_point(y=224.17),
                self.create_key_point(y=218.28),
                self.create_key_point(y=230.07),
                self.create_key_point(y=232.04),
            ])

    def test_is_matching_pose(
            self, pose_matcher, low_confidence, high_confidence):
        assert pose_matcher.is_matching_pose(
            Pose(nose=KeyPoint(y=224.17, x=317.26, confidence=0.56),
                 left_eye=KeyPoint(y=216.31, x=325.12, confidence=0.63),
                 right_eye=KeyPoint(y=218.28, x=301.52, confidence=0.36),
                 left_ear=KeyPoint(y=230.07, x=340.85, confidence=0.63),
                 right_ear=KeyPoint(y=232.04, x=291.04, confidence=0.56),
                 left_shoulder=KeyPoint(y=277.27, x=356.59, confidence=0.70),
                 right_shoulder=KeyPoint(y=283.17, x=267.44, confidence=0.49),
                 left_elbow=KeyPoint(y=230.07, x=411.65, confidence=0.70),
                 right_elbow=KeyPoint(y=228.11, x=201.89, confidence=0.70),
                 left_wrist=KeyPoint(y=145.52, x=411.65, confidence=0.70),
                 right_wrist=KeyPoint(y=155.35, x=183.53, confidence=0.56),
                 left_hip=KeyPoint(y=420.82, x=351.34, confidence=0.19),
                 right_hip=KeyPoint(y=412.96, x=283.17, confidence=0.36),
                 left_knee=KeyPoint(y=479.82, x=356.59, confidence=0.12),
                 right_knee=KeyPoint(y=471.95, x=288.41, confidence=0.07),
                 left_ankle=KeyPoint(y=475.89, x=338.23, confidence=0.07),
                 right_ankle=KeyPoint(y=489.65, x=283.17, confidence=0.07))), \
            'should match pose with high enough confidence'
        # TODO 'should not match pose if too few points have high enough confidence'
        assert not pose_matcher.is_matching_pose(
            Pose(nose=KeyPoint(y=281.20, x=388.05, confidence=0.36),
                 left_eye=KeyPoint(y=259.57, x=424.76, confidence=0.56),
                 right_eye=KeyPoint(y=257.61, x=353.96, confidence=0.56),
                 left_ear=KeyPoint(y=275.30, x=471.95, confidence=0.43),
                 right_ear=KeyPoint(y=277.27, x=293.66, confidence=0.36),
                 left_shoulder=KeyPoint(y=428.69, x=492.93, confidence=0.19),
                 right_shoulder=KeyPoint(y=438.52, x=283.17, confidence=0.19),
                 left_elbow=KeyPoint(y=477.85, x=414.27, confidence=0.12),
                 right_elbow=KeyPoint(y=460.15, x=275.30, confidence=0.12),
                 left_wrist=KeyPoint(y=291.04, x=485.06, confidence=0.02),
                 right_wrist=KeyPoint(y=369.70, x=348.72, confidence=0.09),
                 left_hip=KeyPoint(y=475.89, x=450.98, confidence=0.12),
                 right_hip=KeyPoint(y=481.79, x=73.41, confidence=0.07),
                 left_knee=KeyPoint(y=460.15, x=506.04, confidence=0.09),
                 right_knee=KeyPoint(y=471.95, x=26.21, confidence=0.05),
                 left_ankle=KeyPoint(y=458.19, x=419.51, confidence=0.12),
                 right_ankle=KeyPoint(y=460.15, x=243.84, confidence=0.12))), \
            'should not match different pose'
        assert not pose_matcher.is_matching_pose(
            Pose(nose=KeyPoint(y=176.98, x=235.97, confidence=0.56),
                 left_eye=KeyPoint(y=173.05, x=249.08, confidence=0.63),
                 right_eye=KeyPoint(y=176.98, x=228.11, confidence=0.49),
                 left_ear=KeyPoint(y=171.08, x=259.57, confidence=0.56),
                 right_ear=KeyPoint(y=178.95, x=230.73, confidence=0.43),
                 left_shoulder=KeyPoint(y=200.58, x=259.57, confidence=0.29),
                 right_shoulder=KeyPoint(y=198.61, x=217.62, confidence=0.36),
                 left_elbow=KeyPoint(y=234.01, x=267.44, confidence=0.36),
                 right_elbow=KeyPoint(y=234.01, x=204.51, confidence=0.36),
                 left_wrist=KeyPoint(y=245.81, x=238.60, confidence=0.43),
                 right_wrist=KeyPoint(y=245.81, x=209.75, confidence=0.49),
                 left_hip=KeyPoint(y=263.50, x=259.57, confidence=0.56),
                 right_hip=KeyPoint(y=261.54, x=228.11, confidence=0.56),
                 left_knee=KeyPoint(y=308.73, x=246.46, confidence=0.56),
                 right_knee=KeyPoint(y=304.80, x=225.49, confidence=0.43),
                 left_ankle=KeyPoint(y=353.96, x=249.08, confidence=0.49),
                 right_ankle=KeyPoint(y=357.90, x=212.38, confidence=0.49))), \
            'should not match different pose'
