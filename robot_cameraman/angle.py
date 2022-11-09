def get_delta_angle_clockwise(left: float, right: float) -> float:
    if left <= right:
        return right - left
    return abs(360 - left) % 360 + right


def get_delta_angle_counter_clockwise(left: float, right: float) -> float:
    if left >= right:
        return left - right
    else:
        return abs(360 - right) + left


def get_angle_distance(left: float, right: float) -> float:
    """Returns the smaller delta angle."""
    # To increase floating point precision,
    # get_delta_angle_clockwise and get_delta_angle_counter_clockwise
    # are not reused. Thereby, the required operations to calculate the result
    # can be reduced.
    if left >= right:
        delta = left - right
        if delta <= 180:
            return delta
        return 360 - delta
    delta = abs(360 - right) + left
    if delta <= 180:
        return delta
    return right - left
