# TODO rename parameters to left and right
def get_delta_angle_clockwise(
        current_angle: float, target_angle: float) -> float:
    return abs(360 - current_angle) % 360 + target_angle


def get_delta_angle_counter_clockwise(
        current_angle: float, target_angle: float) -> float:
    if current_angle >= target_angle:
        return current_angle - target_angle
    else:
        return abs(360 - target_angle) + current_angle
