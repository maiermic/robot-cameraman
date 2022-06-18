from robot_cameraman.angle import get_delta_angle_clockwise, \
    get_delta_angle_counter_clockwise


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
