from robot_cameraman.angle import get_delta_angle_clockwise, \
    get_delta_angle_counter_clockwise, get_angle_distance


def test_get_delta_angle_clockwise():
    assert get_delta_angle_clockwise(left=0, right=6) == 6
    assert get_delta_angle_clockwise(left=6, right=0) == 354
    assert get_delta_angle_clockwise(left=0, right=0) == 0
    assert get_delta_angle_clockwise(left=30, right=35) == 5


def test_get_delta_angle_counter_clockwise():
    assert get_delta_angle_counter_clockwise(left=0, right=6) == 354
    assert get_delta_angle_counter_clockwise(left=6, right=0) == 6
    assert get_delta_angle_counter_clockwise(left=0, right=0) == 0
    assert get_delta_angle_counter_clockwise(left=35, right=30) == 5


def test_get_angle_distance():
    assert get_angle_distance(left=0, right=6) == 6
    assert get_angle_distance(left=6, right=0) == 6
    assert get_angle_distance(left=0, right=0) == 0
    assert get_angle_distance(left=30, right=35) == 5
    assert get_angle_distance(left=355, right=6) == 11
    assert get_angle_distance(left=355, right=0) == 5
    assert get_angle_distance(left=0, right=180) == 180
    assert get_angle_distance(left=0, right=181) == 179
    assert get_angle_distance(left=359, right=180) == 179
    assert get_angle_distance(left=359, right=181) == 178
    assert get_angle_distance(left=15.4, right=10.0) == 5.4
    assert get_angle_distance(left=10.0, right=15.4) == 5.4
    assert get_angle_distance(left=0, right=0) == 0
    assert get_angle_distance(left=359.1, right=359.1) == 0
