from robot_cameraman.angle import get_delta_angle_clockwise, \
    get_delta_angle_counter_clockwise


def test_get_delta_angle_clockwise():
    assert 6 == get_delta_angle_clockwise(left=0, right=6)
    assert 354 == get_delta_angle_clockwise(left=6, right=0)
    assert 0 == get_delta_angle_clockwise(left=0, right=0)
    assert 5 == get_delta_angle_clockwise(left=30, right=35)


def test_get_delta_angle_counter_clockwise():
    assert 354 == get_delta_angle_counter_clockwise(left=0, right=6)
    assert 6 == get_delta_angle_counter_clockwise(left=6, right=0)
    assert 0 == get_delta_angle_counter_clockwise(left=0, right=0)
    assert 5 == get_delta_angle_counter_clockwise(left=35, right=30)
