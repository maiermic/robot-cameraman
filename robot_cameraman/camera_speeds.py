from dataclasses import dataclass
from enum import IntEnum


class ZoomSpeed(IntEnum):
    ZOOM_OUT_FAST = -200
    ZOOM_OUT_SLOW = -100
    ZOOM_STOPPED = 0
    ZOOM_IN_SLOW = 100
    ZOOM_IN_FAST = 200


@dataclass
class CameraSpeeds:
    pan_speed: float = 0
    """Speed in degree per second. Positive values mean clockwise,
    negative values stand for counter clockwise moving direction from the
    camera's point of view.
    """

    tilt_speed: float = 0
    """Speed in degree per second. Positive values mean upwards,
    negative values stand for downwards moving direction from the camera's
    point of view.
    """

    zoom_speed: ZoomSpeed = ZoomSpeed.ZOOM_STOPPED
    """Abstract speed unit, i.e. the actual speed depends on camera model.
    Positive values mean camera should zoom in (larger values mean that camera
    should zoom faster), negative values stand for zooming out.
    """

    def reset(self) -> None:
        """Stop camera movements.
        """
        self.pan_speed = 0
        self.tilt_speed = 0
        self.zoom_speed = ZoomSpeed.ZOOM_STOPPED
