# The following factor is used to convert degrees to the units used by the
# SimpleBGC 2.6 serial protocol.
degree_factor = 0.02197265625
degree_per_sec_factor = 0.1220740379


def from_degree(degree: float):
    return int(degree / degree_factor)


def to_degree(angle: float):
    return int(angle * degree_factor)


def from_degree_per_sec(degree_per_sec: float):
    return int(degree_per_sec / degree_per_sec_factor)


def to_degree_per_sec(angle_per_sec: float):
    return int(angle_per_sec * degree_per_sec_factor)
