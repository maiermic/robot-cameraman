from robot_cameraman.angle import get_delta_angle_clockwise, \
    get_delta_angle_counter_clockwise


def test_get_delta_angle_clockwise():
    assert 6 == get_delta_angle_clockwise(
        current_angle=0, target_angle=6)
    assert 354 == get_delta_angle_clockwise(
        current_angle=6, target_angle=0)
    assert 0 == get_delta_angle_clockwise(
        current_angle=0, target_angle=0)


def test_get_delta_angle_counter_clockwise():
    assert 354 == get_delta_angle_counter_clockwise(
        current_angle=0, target_angle=6)
    assert 6 == get_delta_angle_counter_clockwise(
        current_angle=6, target_angle=0)
    assert 0 == get_delta_angle_counter_clockwise(
        current_angle=0, target_angle=0)
