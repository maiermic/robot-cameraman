import math
from typing import Optional


class DistanceEstimator:
    """
    See https://github.com/maiermic/robot-cameraman/issues/13
    """

    _conversion_factor: float
    _focal_length_mm: float
    _image_height_px: int
    _object_height_px: float
    _real_object_height_mm: float
    _sensor_height_mm: float

    distance_of_camera_to_object_mm: float

    def __init__(
            self,
            focal_length_mm: float,
            image_height_px: int,
            object_height_px: float,
            real_object_height_mm: float,
            sensor_height_mm: float) -> None:
        self._focal_length_mm = focal_length_mm
        self._image_height_px = image_height_px
        self._object_height_px = object_height_px
        self._real_object_height_mm = real_object_height_mm
        self._sensor_height_mm = sensor_height_mm
        self._update_factor()

    def _update_factor(self):
        self.distance_of_camera_to_object_mm = \
            (self._focal_length_mm
             * self._real_object_height_mm
             * self._image_height_px
             ) / (self._object_height_px * self._sensor_height_mm)
        self._conversion_factor = \
            (self.distance_of_camera_to_object_mm * self._sensor_height_mm) \
            / (self._focal_length_mm * self._image_height_px)
        # TODO calculation is equivalent to
        # self._conversion_factor = \
        #     self._real_object_height_mm / self._object_height_px

    def configure(
            self,
            focal_length_mm: Optional[float] = None,
            image_height_px: Optional[int] = None,
            object_height_px: Optional[float] = None,
            real_object_height_mm: Optional[float] = None,
            sensor_height_mm: Optional[float] = None) -> None:
        if focal_length_mm is not None:
            self._focal_length_mm = focal_length_mm
        if image_height_px is not None:
            self._image_height_px = image_height_px
        if object_height_px is not None:
            self._object_height_px = object_height_px
        if real_object_height_mm is not None:
            self._real_object_height_mm = real_object_height_mm
        if sensor_height_mm is not None:
            self._sensor_height_mm = sensor_height_mm
        self._update_factor()

    def px_to_mm(self, px: int):
        """
        Convert pixels to millimeter at the same distance of the tracked object.
        The calculation is based on the estimated distance of the tracked object
        to the camera and the size of the tracked object.

        :param px:
        :return:
        """
        return self._conversion_factor * px

    def px_to_image_center_degree_angle(self, px: int):
        """
        Calculate the angle that the camera has to rotate/tilt
        to point to the object (tracking target).

        :param px: Use pixels of x-axis to calculate rotation-angle
        and pixels of y-axis to calculate tilt-angle.
        :return: Angle to rotate/tilt camera to point to the object.
        """
        # distance of object to image center
        a = self.px_to_mm(px)
        b = self.distance_of_camera_to_object_mm
        return math.asin(a / math.sqrt(a * a + b * b)) * 180 / math.pi


def main():
    # example based on measurements
    estimator = DistanceEstimator(
        focal_length_mm=6,
        image_height_px=3000,
        object_height_px=1815,
        real_object_height_mm=2000,
        sensor_height_mm=5.7)
    # expected are ~3500
    print(f"distance_to_object_mm: {estimator.distance_of_camera_to_object_mm}")

    estimator = DistanceEstimator(
        focal_length_mm=6,
        image_height_px=640,
        object_height_px=320,
        real_object_height_mm=1870,
        sensor_height_mm=5.7)

    min_focal_length_angle = estimator.px_to_image_center_degree_angle(100)

    def print_estimate(
            focal_length_mm: float,
            object_height_px: float,
            px: int):
        print("")
        estimator.configure(
            focal_length_mm=focal_length_mm,
            object_height_px=object_height_px)
        print(f"focal length = {focal_length_mm}")
        print(f"object height px = {object_height_px}")
        # noinspection PyProtectedMember
        print(f"conversion factor = {estimator._conversion_factor}")
        print(
            f"distance of camera to object = {estimator.distance_of_camera_to_object_mm}")
        print(f"px = {px}")
        zoom_ratio = focal_length_mm / 6.0
        print(f"zoom ratio = {zoom_ratio}")
        print(
            f"angle (based on distance)   = {estimator.px_to_image_center_degree_angle(px)}")
        print(
            f"angle (based on zoom ratio) = {min_focal_length_angle / zoom_ratio}")

    # object height does not really matter,
    # since the distance/angle to the image center is the same
    # as the object is assumed/estimated to be further away
    # if it is smaller
    print_estimate(
        focal_length_mm=6,
        object_height_px=80,
        px=100)

    # angle depends mainly on zoom ratio
    print_estimate(
        focal_length_mm=6,
        object_height_px=320,
        px=100)
    print_estimate(
        focal_length_mm=12,
        object_height_px=320,
        px=100)
    print_estimate(
        focal_length_mm=18,
        object_height_px=320,
        px=100)
    print_estimate(
        focal_length_mm=24,
        object_height_px=320,
        px=100)


if __name__ == '__main__':
    main()
