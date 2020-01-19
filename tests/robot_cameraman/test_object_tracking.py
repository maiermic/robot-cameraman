import pytest

from robot_cameraman.box import Box, Point
from robot_cameraman.image_detection import DetectionCandidate
from robot_cameraman.object_tracking import ObjectTracker


@pytest.fixture()
def object_tracker():
    return ObjectTracker()


@pytest.fixture()
def first_object_id():
    return 0


@pytest.fixture()
def second_object_id():
    return 1


@pytest.fixture()
def third_object_id():
    return 2


def make_candidate_from_coordinates(x1: float, y1: float, x2: float, y2: float):
    return DetectionCandidate(label_id=0, score=1,
                              bounding_box=Box.from_coordinates(x1, y1, x2, y2))


def make_candidate_from_center_and_size(
        center: Point, width: float, height: float):
    box = Box.from_center_and_size(center, width, height)
    return DetectionCandidate(label_id=0, score=1, bounding_box=box)


def test_no_id_is_registered_by_default(object_tracker):
    assert not object_tracker.is_registered(0)
    assert not object_tracker.is_registered(1)


def test_update_registers_candidate_with_fresh_id(
        object_tracker, first_object_id):
    assert not object_tracker.is_registered(first_object_id)
    c0 = make_candidate_from_coordinates(0, 0, 10, 10)
    candidates = object_tracker.update([c0])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c0
    assert object_tracker.is_registered(first_object_id)


def test_candidate_is_updated(
        object_tracker, first_object_id):
    assert not object_tracker.is_registered(first_object_id)
    c0 = make_candidate_from_coordinates(0, 0, 10, 10)
    candidates = object_tracker.update([c0])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c0
    assert object_tracker.is_registered(first_object_id)
    c1 = make_candidate_from_coordinates(0, 0, 11, 11)
    candidates = object_tracker.update([c1])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c1
    assert object_tracker.is_registered(first_object_id)


def test_candidate_is_deregistered_if_max_disappeared_is_exceeded(
        first_object_id):
    object_tracker = ObjectTracker(max_disappeared=1)
    assert not object_tracker.is_registered(first_object_id)
    c0 = make_candidate_from_coordinates(0, 0, 10, 10)
    candidates = object_tracker.update([c0])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c0
    assert object_tracker.is_registered(first_object_id)
    candidates = object_tracker.update([])
    assert first_object_id not in candidates
    assert object_tracker.is_registered(first_object_id)
    candidates = object_tracker.update([])
    assert first_object_id not in candidates
    assert not object_tracker.is_registered(first_object_id), \
        'object should be deregistered'


def test_candidate_further_apart_is_seen_as_another_object(
        object_tracker, first_object_id, second_object_id):
    c0 = make_candidate_from_center_and_size(Point(10, 10), 10, 10)
    c1 = make_candidate_from_center_and_size(Point(111, 10), 10, 10)
    candidates = object_tracker.update([c0])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c0
    assert object_tracker.is_registered(first_object_id)
    candidates = object_tracker.update([c1])
    assert second_object_id in candidates
    assert first_object_id not in candidates
    assert candidates[second_object_id] == c1
    assert object_tracker.is_registered(first_object_id)
    assert object_tracker.is_registered(second_object_id)


def test_mostly_overlapping_candidates_are_seen_as_the_same_object(
        object_tracker, first_object_id, second_object_id):
    c0 = make_candidate_from_center_and_size(Point(10, 10), 10, 10)
    c1 = make_candidate_from_center_and_size(Point(111, 10), 200, 10)
    # Candidates would be to far apart to be seen as the same
    assert 101 == c0.bounding_box.center.distance_to(c1.bounding_box.center)
    # but not if they overlap for the most part. The following assertion shows
    # that the bounding boxes overlap by 40%
    assert 0.4 == c0.bounding_box.percental_intersection_area(c1.bounding_box)
    candidates = object_tracker.update([c0])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c0
    assert object_tracker.is_registered(first_object_id)
    candidates = object_tracker.update([c1])
    assert second_object_id not in candidates
    assert first_object_id in candidates
    assert candidates[first_object_id] == c1
    assert object_tracker.is_registered(first_object_id)
    assert not object_tracker.is_registered(second_object_id)


def test_update_registers_each_candidate_with_fresh_id(
        object_tracker, first_object_id, second_object_id):
    assert not object_tracker.is_registered(first_object_id)
    assert not object_tracker.is_registered(second_object_id)
    c0 = make_candidate_from_center_and_size(Point(10, 10), 10, 10)
    c1 = make_candidate_from_center_and_size(Point(600, 10), 10, 10)
    candidates = object_tracker.update([c0, c1])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c0
    assert object_tracker.is_registered(first_object_id)
    assert second_object_id in candidates
    assert candidates[second_object_id] == c1
    assert object_tracker.is_registered(second_object_id)


def test_update_associates_closer_object_with_candidate(
        object_tracker, first_object_id, second_object_id, third_object_id):
    c0 = make_candidate_from_center_and_size(Point(10, 10), 10, 10)
    c1 = make_candidate_from_center_and_size(Point(600, 10), 10, 10)
    c2 = make_candidate_from_center_and_size(Point(20, 10), 10, 10)
    # c2 is closer to c0 than to c1
    dist_c2_to_c0 = c2.bounding_box.center.distance_to(c0.bounding_box.center)
    dist_c2_to_c1 = c2.bounding_box.center.distance_to(c1.bounding_box.center)
    assert dist_c2_to_c0 < dist_c2_to_c1
    candidates = object_tracker.update([c0, c1])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c0
    assert object_tracker.is_registered(first_object_id)
    assert second_object_id in candidates
    assert candidates[second_object_id] == c1
    assert object_tracker.is_registered(second_object_id)
    candidates = object_tracker.update([c2])
    assert third_object_id not in candidates
    assert first_object_id in candidates
    assert candidates[first_object_id] == c2
    assert object_tracker.is_registered(first_object_id)
    assert second_object_id not in candidates
    assert object_tracker.is_registered(second_object_id)


def test_non_overlapping_candidate_differs_too_much_in_size_to_be_same_object(
        object_tracker, first_object_id, second_object_id):
    c0 = make_candidate_from_coordinates(0, 0, 5, 5)
    c1 = make_candidate_from_coordinates(6, 0, 16, 10.1)
    # assert precondition: size changed by a factor greater than 4,
    # i.e. c1 differs too much in size to be the same object as c0
    assert c0.bounding_box.area() == 25
    assert c1.bounding_box.area() == 101

    candidates = object_tracker.update([c0])
    assert first_object_id in candidates
    assert candidates[first_object_id] == c0
    assert object_tracker.is_registered(first_object_id)
    candidates = object_tracker.update([c1])
    assert second_object_id in candidates
    assert first_object_id not in candidates
    assert candidates[second_object_id] == c1
    assert object_tracker.is_registered(first_object_id)
    assert object_tracker.is_registered(second_object_id)
