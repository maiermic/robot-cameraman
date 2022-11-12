from unittest.mock import Mock

import pytest

from robot_cameraman.box import Box
from robot_cameraman.image_detection import DetectionCandidate
from robot_cameraman.target_selection import SelectFirstTargetStrategy, \
    Target, SelectTargetAtCoordinateStrategy


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
