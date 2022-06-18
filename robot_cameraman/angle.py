def get_delta_angle_clockwise(left: float, right: float) -> float:
    if left <= right:
        return right - left
    return abs(360 - left) % 360 + right


def get_delta_angle_counter_clockwise(left: float, right: float) -> float:
    if left >= right:
        return left - right
    else:
        return abs(360 - right) + left
