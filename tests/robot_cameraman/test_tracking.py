import pytest
from unittest.mock import Mock

from robot_cameraman.box import Box, Point
from robot_cameraman.camera_controller import CameraZoomIndexLimitController, \
    CameraAngleLimitController
from robot_cameraman.camera_speeds import CameraSpeeds, ZoomSpeed
from robot_cameraman.gimbal import Angles
from robot_cameraman.live_view import ImageSize
from robot_cameraman.tracking import StaticSearchTargetStrategy, \
    ConfigurableAlignTrackingStrategy, Destination
from robot_cameraman.zoom_limits import ZoomLimits


class TestConfigurableAlignTrackingStrategy:
    @pytest.fixture()
    def image_size(self):
        return ImageSize(width=640, height=480)

    @pytest.fixture()
    def destination(self, image_size):
        return Destination(image_size)

    def test_is_aligned(self, image_size, destination):
        strategy = ConfigurableAlignTrackingStrategy(
            destination=destination,
            image_size=image_size,
            max_allowed_speed=42)
        self.assert_is_aligned(destination, strategy)

    def assert_is_aligned(
            self,
            destination,
            strategy,
            is_max_zoom_reached=False,
            is_min_zoom_reached=False):
        assert strategy.is_aligned(
            Box.from_center_and_size(
                center=destination.center, width=120, height=240))
        if is_min_zoom_reached:
            assert strategy.is_aligned(
                Box.from_center_and_size(
                    center=destination.center, width=180, height=360)), \
                ('target should be aligned (even though it is too large),'
                 'since camera can not zoom in any further')
        else:
            assert not strategy.is_aligned(
                Box.from_center_and_size(
                    center=destination.center, width=180, height=360)), \
                'target should be too large (in height) to be aligned'
        if is_max_zoom_reached:
            assert strategy.is_aligned(
                Box.from_center_and_size(
                    center=destination.center, width=60, height=120)), \
                ('target should be aligned (even though it is too small),'
                 'since camera can not zoom out any further')
        else:
            assert not strategy.is_aligned(
                Box.from_center_and_size(
                    center=destination.center, width=60, height=120)), \
                'target should be too small (in height) to be aligned'
        assert not strategy.is_aligned(
            Box.from_center_and_size(
                Point(x=60, y=destination.center.y), width=120, height=240)), \
            'target should be too far to the left to be aligned'
        assert not strategy.is_aligned(
            Box.from_center_and_size(
                Point(x=500, y=destination.center.y), width=120, height=240)), \
            'target should be too far to the right to be aligned'
        assert not strategy.is_aligned(
            Box.from_center_and_size(
                Point(x=destination.center.x, y=120), width=120, height=240)), \
            'target should be too far up to be aligned'
        assert not strategy.is_aligned(
            Box.from_center_and_size(
                Point(x=destination.center.x, y=360), width=120, height=240)), \
            'target should be too far down to be aligned'

    def test_is_aligned_considering_zoom_limits(
            self, image_size, destination):
        zoom_limits = Mock(spec=ZoomLimits)
        strategy = ConfigurableAlignTrackingStrategy(
            destination=destination,
            image_size=image_size,
            max_allowed_speed=42,
            zoom_limits=zoom_limits)

        def assert_is_aligned(
                current_zoom_ratio: float,
                is_max_zoom_reached=False,
                is_min_zoom_reached=False):
            zoom_limits.update_current_zoom_ratio = \
                Mock(return_value=current_zoom_ratio)
            zoom_limits.is_max_zoom_reached = \
                Mock(return_value=is_max_zoom_reached)
            zoom_limits.is_min_zoom_reached = \
                Mock(return_value=is_min_zoom_reached)
            self.assert_is_aligned(
                destination,
                strategy,
                is_min_zoom_reached=is_min_zoom_reached,
                is_max_zoom_reached=is_max_zoom_reached)

        assert_is_aligned(current_zoom_ratio=2.0)
        assert_is_aligned(current_zoom_ratio=1.0,
                          is_min_zoom_reached=True)
        assert_is_aligned(current_zoom_ratio=14.3,
                          is_max_zoom_reached=True)


class TestStaticSearchTargetStrategy:
    @pytest.fixture()
    def camera_speeds(self):
        return CameraSpeeds()

    @pytest.fixture()
    def camera_zoom_limit_controller(self):
        return CameraZoomIndexLimitController()

    @pytest.fixture()
    def camera_angle_limit_controller(self):
        return CameraAngleLimitController()

    @pytest.fixture()
    def max_pan_speed(self):
        return 9

    @pytest.fixture()
    def max_tilt_speed(self):
        return 9

    @pytest.fixture()
    def search_target_strategy(
            self,
            camera_zoom_limit_controller,
            camera_angle_limit_controller,
            max_pan_speed,
            max_tilt_speed):
        return StaticSearchTargetStrategy(
            pan_speed=max_pan_speed,
            tilt_speed=max_tilt_speed,
            camera_zoom_limit_controller=camera_zoom_limit_controller,
            camera_angle_limit_controller=camera_angle_limit_controller)

    @pytest.fixture()
    def update_current_camera_state(
            self,
            search_target_strategy,
            camera_speeds,
            max_pan_speed,
            max_tilt_speed,
            camera_zoom_limit_controller,
            camera_angle_limit_controller):
        def update_current_camera_state(
                pan_angle: float,
                pan_speed: float,
                tilt_angle: float,
                tilt_speed: float,
                zoom_index: int,
                zoom_ratio: float):
            angles = Angles(pan_angle=pan_angle, pan_speed=pan_speed,
                            tilt_angle=tilt_angle, tilt_speed=tilt_speed)
            search_target_strategy.update_current_angles(angles)
            search_target_strategy.update_current_zoom_index(zoom_index)
            search_target_strategy.update_current_zoom_ratio(zoom_ratio)

            camera_angle_limit_controller.update_current_angles(angles)

            camera_zoom_limit_controller.update_zoom_index(zoom_index)

        return update_current_camera_state

    def test_update_moves_to_target_from_left(
            self,
            search_target_strategy,
            camera_speeds,
            max_pan_speed,
            max_tilt_speed,
            update_current_camera_state):
        update_current_camera_state(
            pan_angle=0,
            pan_speed=0,
            tilt_angle=0,
            tilt_speed=0,
            zoom_index=0,
            zoom_ratio=1.0)
        search_target_strategy.update_target(
            pan_angle=10.0,
            tilt_angle=15.0,
            zoom_index=20,
            zoom_ratio=None)

        search_target_strategy.start()

        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == max_pan_speed
        assert camera_speeds.tilt_speed == max_tilt_speed
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_IN_SLOW

        # target is quite close => camera should pan/tilt slower:
        #   max_speed / ratio + "percentage based on distance"
        update_current_camera_state(
            pan_angle=3.25,
            pan_speed=max_pan_speed,
            tilt_angle=8.25,
            tilt_speed=max_tilt_speed,
            zoom_index=11,
            zoom_ratio=2.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == 6.75  # distance to target
        assert camera_speeds.tilt_speed == 6.75  # distance to target
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_IN_SLOW

        # target is close
        #  => camera should pan/tilt even slower (according to zoom ratio):
        #       max_speed / ratio
        update_current_camera_state(
            pan_angle=8,
            pan_speed=max_pan_speed,
            tilt_angle=13,
            tilt_speed=max_tilt_speed,
            zoom_index=17,
            zoom_ratio=3.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == max_pan_speed / 3.0
        assert camera_speeds.tilt_speed == max_tilt_speed / 3.0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_IN_SLOW

        # reach target
        update_current_camera_state(
            pan_angle=10.0,
            pan_speed=max_pan_speed,
            tilt_angle=15.0,
            tilt_speed=max_tilt_speed,
            zoom_index=20,
            zoom_ratio=4.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == 0
        assert camera_speeds.tilt_speed == 0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        search_target_strategy.stop()

        # Strategy should consider that angles may pass over 360 to 0.
        # Strategy should consider that zoom target might already be reached.
        update_current_camera_state(
            pan_angle=359,
            pan_speed=0,
            tilt_angle=351,
            tilt_speed=0,
            zoom_index=0,
            zoom_ratio=1.0)
        search_target_strategy.update_target(
            pan_angle=10.0,
            tilt_angle=5.0,
            zoom_index=0,
            zoom_ratio=None)

        search_target_strategy.start()

        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == max_pan_speed
        assert camera_speeds.tilt_speed == max_tilt_speed
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        # reach target
        update_current_camera_state(
            pan_angle=10.0,
            pan_speed=max_pan_speed,
            tilt_angle=5.0,
            tilt_speed=max_tilt_speed,
            zoom_index=21,
            zoom_ratio=4.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == 0
        assert camera_speeds.tilt_speed == 0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        search_target_strategy.stop()

    def test_update_moves_to_target_from_right(
            self,
            search_target_strategy,
            camera_speeds,
            max_pan_speed,
            max_tilt_speed,
            update_current_camera_state):
        update_current_camera_state(
            pan_angle=20.0,
            pan_speed=0,
            tilt_angle=15.0,
            tilt_speed=0,
            zoom_index=40,
            zoom_ratio=10.0)
        search_target_strategy.update_target(
            pan_angle=10.0,
            tilt_angle=5.0,
            zoom_index=20,
            zoom_ratio=None)

        search_target_strategy.start()

        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == -max_pan_speed
        assert camera_speeds.tilt_speed == -max_tilt_speed
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_OUT_SLOW

        # target is quite close => camera should pan/tilt slower:
        #   max_speed / ratio + "percentage based on distance"
        update_current_camera_state(
            pan_angle=16.75,
            pan_speed=max_pan_speed,
            tilt_angle=11.75,
            tilt_speed=max_tilt_speed,
            zoom_index=30,
            zoom_ratio=6.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == -6.75  # distance to target
        assert camera_speeds.tilt_speed == -6.75  # distance to target
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_OUT_SLOW

        # target is close
        #  => camera should pan/tilt even slower (according to zoom ratio):
        #       max_speed / ratio
        update_current_camera_state(
            pan_angle=11.5,
            pan_speed=max_pan_speed,
            tilt_angle=6.5,
            tilt_speed=max_tilt_speed,
            zoom_index=25,
            zoom_ratio=5.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == -max_pan_speed / 5.0
        assert camera_speeds.tilt_speed == -max_tilt_speed / 5.0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_OUT_SLOW

        # reach target
        update_current_camera_state(
            pan_angle=10.0,
            pan_speed=-max_pan_speed,
            tilt_angle=5.0,
            tilt_speed=-max_tilt_speed,
            zoom_index=20,
            zoom_ratio=4.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == 0
        assert camera_speeds.tilt_speed == 0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        search_target_strategy.stop()

        # Strategy should consider that angles may pass over 360 to 0.
        # Strategy should consider that zoom target might already be reached.
        update_current_camera_state(
            pan_angle=1,
            pan_speed=0,
            tilt_angle=11,
            tilt_speed=0,
            zoom_index=0,
            zoom_ratio=1.0)
        search_target_strategy.update_target(
            pan_angle=351.0,
            tilt_angle=356.0,
            zoom_index=0,
            zoom_ratio=None)

        search_target_strategy.start()

        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == -max_pan_speed
        assert camera_speeds.tilt_speed == -max_tilt_speed
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        # reach target
        update_current_camera_state(
            pan_angle=351.0,
            pan_speed=-max_pan_speed,
            tilt_angle=356.0,
            tilt_speed=-max_tilt_speed,
            zoom_index=0,
            zoom_ratio=1.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == 0
        assert camera_speeds.tilt_speed == 0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        search_target_strategy.stop()

    def test_update_does_not_move_before_target_is_set(
            self,
            search_target_strategy,
            camera_speeds,
            max_pan_speed,
            max_tilt_speed,
            update_current_camera_state):
        update_current_camera_state(
            pan_angle=0,
            pan_speed=0,
            tilt_angle=0,
            tilt_speed=0,
            zoom_index=0,
            zoom_ratio=1.0)

        search_target_strategy.start()

        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == 0
        assert camera_speeds.tilt_speed == 0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        search_target_strategy.update_target(
            pan_angle=30.0,
            tilt_angle=15.0,
            zoom_index=20,
            zoom_ratio=None)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == max_pan_speed
        assert camera_speeds.tilt_speed == max_tilt_speed
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_IN_SLOW

    def test_update_does_not_move_before_current_angles_are_set(
            self,
            search_target_strategy,
            camera_speeds,
            max_pan_speed,
            max_tilt_speed,
            update_current_camera_state):
        search_target_strategy.start()

        search_target_strategy.update_target(
            pan_angle=30.0,
            tilt_angle=15.0,
            zoom_index=20,
            zoom_ratio=None)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == 0
        assert camera_speeds.tilt_speed == 0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        update_current_camera_state(
            pan_angle=0,
            pan_speed=0,
            tilt_angle=0,
            tilt_speed=0,
            zoom_index=0,
            zoom_ratio=1.0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == max_pan_speed
        assert camera_speeds.tilt_speed == max_tilt_speed
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_IN_SLOW

    def test_update_does_not_zoom_before_current_zoom_is_set(
            self,
            search_target_strategy,
            camera_angle_limit_controller,
            camera_zoom_limit_controller,
            camera_speeds,
            max_pan_speed,
            max_tilt_speed,
            update_current_camera_state):
        search_target_strategy.start()

        search_target_strategy.update_target(
            pan_angle=30.0,
            tilt_angle=15.0,
            zoom_index=20,
            zoom_ratio=None)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == 0
        assert camera_speeds.tilt_speed == 0
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        # only update angles
        angles = Angles(pan_angle=0, pan_speed=0, tilt_angle=0, tilt_speed=0)
        search_target_strategy.update_current_angles(angles)
        camera_angle_limit_controller.update_current_angles(angles)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == max_pan_speed
        assert camera_speeds.tilt_speed == max_tilt_speed
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_STOPPED

        search_target_strategy.update_current_zoom_index(0)
        search_target_strategy.update_current_zoom_ratio(1.0)
        camera_zoom_limit_controller.update_zoom_index(0)
        search_target_strategy.update(camera_speeds)
        assert camera_speeds.pan_speed == max_pan_speed
        assert camera_speeds.tilt_speed == max_tilt_speed
        assert camera_speeds.zoom_speed == ZoomSpeed.ZOOM_IN_SLOW
