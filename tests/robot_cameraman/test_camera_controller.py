from unittest.mock import Mock

import pytest

from robot_cameraman.camera_controller import \
    BaseCamPathOfMotionCameraController, PointOfMotion, SpeedManager, \
    ElapsedTime
from robot_cameraman.tracking import CameraSpeeds
from simplebgc.commands import GetAnglesInCmd
from simplebgc.gimbal import Gimbal, ControlMode
from simplebgc.units import from_degree, from_degree_per_sec


def get_angles_in_cmd(pan_angle: int, pan_speed: int,
                      tilt_angle: int, tilt_speed: int):
    return GetAnglesInCmd(
        imu_angle_1=0,
        target_angle_1=0,
        target_speed_1=0,
        imu_angle_2=from_degree(tilt_angle),
        target_angle_2=from_degree(tilt_angle),
        target_speed_2=from_degree_per_sec(tilt_speed),
        imu_angle_3=from_degree(pan_angle),
        target_angle_3=from_degree(pan_angle),
        target_speed_3=from_degree_per_sec(pan_speed))


def create_speed_manager_mock():
    sm = Mock(spec=SpeedManager())
    sm.current_speed = 0
    sm.target_speed = 0
    sm.is_target_speed_reached = Mock(
        side_effect=lambda: sm.current_speed == sm.target_speed)
    sm.reset = Mock()
    sm.acceleration_per_second = 0

    def update():
        if sm.current_speed < sm.target_speed:
            sm.current_speed = min(
                sm.current_speed + sm.acceleration_per_second,
                sm.target_speed)
        elif sm.current_speed > sm.target_speed:
            sm.current_speed = max(
                sm.current_speed - sm.acceleration_per_second,
                sm.target_speed)
        return sm.current_speed

    sm.update = Mock(side_effect=update)
    return sm


def should_not_be_called_mock(name: str):
    return Mock(side_effect=RuntimeError(f'{name} should not be called'))


class TestSpeedManager:
    @pytest.fixture()
    def acceleration(self):
        return 1

    @pytest.fixture()
    def elapsed_time(self):
        elapsed_time = Mock(spec=ElapsedTime())
        elapsed_time.update = Mock(return_value=1)
        return elapsed_time

    @pytest.fixture()
    def speed_manager(self, acceleration, elapsed_time):
        return SpeedManager(acceleration_per_second=acceleration,
                            elapsed_time=elapsed_time)

    def test_reset(self, speed_manager, elapsed_time):
        speed_manager.reset()
        assert elapsed_time.reset.call_count == 1

    def test_is_target_speed_reached(self, speed_manager, elapsed_time):
        speed_manager.reset()
        assert elapsed_time.reset.call_count == 1

    def test_speed_manager(self, speed_manager):
        self.run_test_of_speed_manager(speed_manager)

    def test_speed_manager_mock(self):
        self.run_test_of_speed_manager(create_speed_manager_mock())

    @staticmethod
    def run_test_of_speed_manager(speed_manager):
        speed_manager.acceleration_per_second = 0
        assert speed_manager.current_speed == 0
        assert speed_manager.target_speed == 0
        assert speed_manager.is_target_speed_reached()
        assert speed_manager.update() == 0 == speed_manager.current_speed
        assert speed_manager.is_target_speed_reached()

        assert speed_manager.acceleration_per_second == 0
        speed_manager.current_speed = 3
        assert not speed_manager.is_target_speed_reached()
        assert speed_manager.update() == 3 == speed_manager.current_speed
        assert not speed_manager.is_target_speed_reached()

        speed_manager.acceleration_per_second = 2
        assert not speed_manager.is_target_speed_reached()
        # target speed is lower than current speed => decrease speed
        assert speed_manager.update() == 1 == speed_manager.current_speed
        assert not speed_manager.is_target_speed_reached()
        # target speed is lower than current speed
        #   => decrease speed, but do not overshoot
        assert speed_manager.update() == 0 == speed_manager.current_speed
        assert speed_manager.is_target_speed_reached()
        # target speed is equal to current speed => keep speed
        assert speed_manager.update() == 0 == speed_manager.current_speed
        assert speed_manager.is_target_speed_reached()

        speed_manager.target_speed = 3
        assert not speed_manager.is_target_speed_reached()
        # target speed is greater than current speed => increase speed
        assert speed_manager.update() == 2 == speed_manager.current_speed
        assert not speed_manager.is_target_speed_reached()
        # target speed is greater than current speed
        #   => increase speed, but do not overshoot
        assert speed_manager.update() == 3 == speed_manager.current_speed
        assert speed_manager.is_target_speed_reached()
        # target speed is equal to current speed => keep speed
        assert speed_manager.update() == 3 == speed_manager.current_speed
        assert speed_manager.is_target_speed_reached()


class TestBaseCamPathOfMotionCameraController:
    @pytest.fixture()
    def gimbal(self):
        # mock serial connection to avoid error, because port can not be opened
        return Mock(spec=Gimbal(Mock()))

    @pytest.fixture()
    def rotate_speed_manager(self):
        return create_speed_manager_mock()

    @pytest.fixture()
    def tilt_speed_manager(self):
        return create_speed_manager_mock()

    @pytest.fixture()
    def controller(self, gimbal, rotate_speed_manager, tilt_speed_manager):
        return BaseCamPathOfMotionCameraController(
            gimbal, rotate_speed_manager, tilt_speed_manager)

    @pytest.fixture()
    def camera_speeds(self):
        return CameraSpeeds()

    @pytest.fixture()
    def zero_angles(self):
        return get_angles_in_cmd(pan_angle=0, pan_speed=0,
                                 tilt_angle=0, tilt_speed=0)

    @pytest.fixture()
    def get_zero_angles(self, zero_angles):
        return Mock(return_value=zero_angles)

    @pytest.fixture()
    def zero_point(self):
        return PointOfMotion(pan_angle=0, tilt_angle=0)

    @pytest.fixture()
    def non_zero_point(self):
        return PointOfMotion(pan_angle=180, tilt_angle=30)

    def test_fixture_points(self, zero_point, non_zero_point):
        assert zero_point != non_zero_point

    def test_target_speeds_are_set_in_constructor(self, controller):
        assert controller._rotate_speed_manager.target_speed == 60
        assert controller._tilt_speed_manager.target_speed == 12

    def test_empty_path_has_no_points(self, controller):
        assert not controller.has_points()

    def test_empty_path_has_not_next_points(self, controller):
        assert not controller.has_next_point()

    def test_end_of_empty_path_is_reached(self, controller):
        assert controller.is_end_of_path_reached()

    def test_end_of_single_point_path_is_not_reached(
            self, controller, gimbal, get_zero_angles, non_zero_point,
            camera_speeds):
        gimbal.get_angles = should_not_be_called_mock('gimbal.get_angles')
        controller.add_point(non_zero_point)
        assert not controller.is_end_of_path_reached()
        gimbal.get_angles = get_zero_angles
        controller.update(camera_speeds)
        assert not controller.is_end_of_path_reached()

    def test_end_of_single_point_path_is_reached(
            self, controller, gimbal, get_zero_angles, zero_point,
            camera_speeds):
        gimbal.get_angles = should_not_be_called_mock('gimbal.get_angles')
        controller.add_point(zero_point)
        assert not controller.is_end_of_path_reached()
        gimbal.get_angles = get_zero_angles
        controller.update(camera_speeds)
        assert controller.is_end_of_path_reached()

    def test_end_of_multi_point_path_is_reached(
            self, controller, gimbal, get_zero_angles, zero_point,
            non_zero_point,
            camera_speeds):
        gimbal.get_angles = should_not_be_called_mock('gimbal.get_angles')
        controller.add_point(zero_point)
        controller.add_point(non_zero_point)
        assert not controller.is_end_of_path_reached()
        gimbal.get_angles = get_zero_angles
        controller.update(camera_speeds)
        assert not controller.is_end_of_path_reached()
        assert controller.current_point() == non_zero_point
        # still at the same angle as before, i.e. end not reached yet
        controller.update(camera_speeds)
        assert not controller.is_end_of_path_reached()
        # angle of last point is reached
        gimbal.get_angles = Mock(
            return_value=get_angles_in_cmd(
                pan_angle=non_zero_point.pan_angle, pan_speed=0,
                tilt_angle=non_zero_point.tilt_angle, tilt_speed=0))
        controller.update(camera_speeds)
        gimbal.get_angles = should_not_be_called_mock('gimbal.get_angles')
        assert controller.is_end_of_path_reached()

    def test_start_resets_speed_managers(
            self, controller, rotate_speed_manager: Mock,
            tilt_speed_manager: Mock):
        controller.start()
        assert rotate_speed_manager.reset.call_count == 1
        assert tilt_speed_manager.reset.call_count == 1

    def test_update_empty_path(self, controller, camera_speeds):
        controller.start()
        controller.update(camera_speeds)
        assert camera_speeds == CameraSpeeds()

    def test_path_has_points(self, controller, zero_point):
        controller.add_point(zero_point)
        assert controller.has_points()

    def test_single_point_path_has_no_next_point(self, controller, zero_point):
        controller.add_point(zero_point)
        assert not controller.has_next_point()

    def test_multi_point_path_has_next_point(
            self, controller, zero_point, non_zero_point):
        controller.add_point(zero_point)
        controller.add_point(non_zero_point)
        assert controller.has_next_point()

    def test_multi_point_path_has_no_next_point(
            self, controller, zero_point, non_zero_point):
        controller.add_point(zero_point)
        controller.add_point(non_zero_point)
        controller.next_point()
        assert not controller.has_next_point()

    def test_current_point(self, controller, zero_point, non_zero_point):
        controller.add_point(zero_point)
        assert controller.current_point() == zero_point
        controller.add_point(non_zero_point)
        assert controller.current_point() == zero_point

    def test_next_point(self, controller, zero_point, non_zero_point):
        controller.add_point(zero_point)
        controller.add_point(non_zero_point)
        assert controller.current_point() == zero_point
        controller.next_point()
        assert controller.current_point() == non_zero_point

    def test_update_of_empty_path(self, controller, camera_speeds, gimbal,
                                  zero_angles, get_zero_angles):
        gimbal.get_angles = get_zero_angles
        controller.start()
        controller.update(camera_speeds)
        assert gimbal.get_angles.call_count == 0
        assert camera_speeds == CameraSpeeds()

    # Also tests that gimbal stops when last point is reached,
    # since no control-command is sent that could overwrite the last command,
    # which has the last point as target.
    def test_do_not_move_if_point_is_already_reached(
            self, controller, camera_speeds, gimbal, zero_point,
            get_zero_angles, rotate_speed_manager, tilt_speed_manager):
        gimbal.get_angles = get_zero_angles
        gimbal.control = Mock()
        controller.add_point(zero_point)
        controller.start()
        assert gimbal.get_angles.call_count == 0

        controller.update(camera_speeds)
        # point is reached => do not send any control command to gimbal
        assert gimbal.control.call_count == 0
        # required to check if point is reached
        assert gimbal.get_angles.call_count == 1
        # speed should not be increased
        assert rotate_speed_manager.update.call_count == 0
        assert tilt_speed_manager.update.call_count == 0
        assert camera_speeds == CameraSpeeds()

    def test_move_to_point_with_minimum_speed(
            self, controller, camera_speeds, gimbal, get_zero_angles,
            non_zero_point):
        gimbal.get_angles = get_zero_angles
        gimbal.control = Mock()
        controller.add_point(non_zero_point)

        controller.start()
        assert gimbal.get_angles.call_count == 0
        assert gimbal.control.call_count == 0

        # should move with minimum speed (target speed is zero) to first point
        controller.update(camera_speeds)
        assert gimbal.get_angles.call_count == 1
        assert gimbal.control.call_count == 1
        min_speed = 1
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle, yaw_speed=min_speed,
            yaw_angle=non_zero_point.pan_angle,
            pitch_mode=ControlMode.angle, pitch_speed=min_speed,
            pitch_angle=non_zero_point.tilt_angle)
        assert camera_speeds == CameraSpeeds()

    def test_move_with_increasing_speed_to_point(
            self, controller, camera_speeds, gimbal, get_zero_angles,
            rotate_speed_manager, tilt_speed_manager):
        gimbal.get_angles = get_zero_angles
        gimbal.control = Mock()
        rotate_speed_manager.acceleration_per_second = 30
        tilt_speed_manager.acceleration_per_second = 6
        current_point = PointOfMotion(pan_angle=21, tilt_angle=6)
        next_point = PointOfMotion(pan_angle=0, tilt_angle=0)

        controller.add_point(current_point)
        controller.add_point(next_point)

        controller.start()
        assert gimbal.get_angles.call_count == 0
        assert gimbal.control.call_count == 0

        # should move with speeds of speed managers to first point
        controller.update(camera_speeds)
        assert gimbal.get_angles.call_count == 1
        assert gimbal.control.call_count == 1
        assert rotate_speed_manager.current_speed == 30
        assert tilt_speed_manager.current_speed == 6
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=rotate_speed_manager.current_speed,
            yaw_angle=current_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=tilt_speed_manager.current_speed,
            pitch_angle=current_point.tilt_angle)
        assert not controller.is_target_speed_reached()

        gimbal.get_angles = Mock(
            return_value=get_angles_in_cmd(pan_angle=7, pan_speed=30,
                                           tilt_angle=2, tilt_speed=6))
        gimbal.control.reset_mock()
        # should increase speeds till target speeds are reached
        controller.update(camera_speeds)
        assert gimbal.get_angles.call_count == 1
        assert rotate_speed_manager.current_speed == 60
        assert tilt_speed_manager.current_speed == 12
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=rotate_speed_manager.current_speed,
            yaw_angle=current_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=tilt_speed_manager.current_speed,
            pitch_angle=current_point.tilt_angle)
        assert controller.is_target_speed_reached()

        # reset mocks, since their call counts are checked later
        gimbal.control.reset_mock()
        rotate_speed_manager.update.reset_mock()
        rotate_speed_manager.reset.reset_mock()
        tilt_speed_manager.update.reset_mock()
        tilt_speed_manager.reset.reset_mock()

        gimbal.get_angles = Mock(
            return_value=get_angles_in_cmd(pan_angle=14, pan_speed=60,
                                           tilt_angle=4, tilt_speed=12))
        # target speeds are reached, but target is not reached yet
        controller.update(camera_speeds)
        # call to get_angles required to check if target is reached
        assert gimbal.get_angles.call_count == 1
        # target speed already reached => no control command needs to be sent
        assert gimbal.control.call_count == 0
        # but time of speed managers has to be updated
        assert (rotate_speed_manager.update.call_count == 1
                or rotate_speed_manager.reset.call_count == 1)
        assert (tilt_speed_manager.update.call_count == 1
                or tilt_speed_manager.reset.call_count == 1)
        assert controller.current_point() == current_point

    def test_move_to_next_point_when_current_point_is_reached(
            self, controller, camera_speeds, gimbal, get_zero_angles,
            rotate_speed_manager, tilt_speed_manager):
        gimbal.control = Mock()
        rotate_speed_manager.acceleration_per_second = 30
        rotate_speed_manager.current_speed = rotate_speed_manager.target_speed
        tilt_speed_manager.acceleration_per_second = 6
        tilt_speed_manager.current_speed = tilt_speed_manager.target_speed
        current_point = PointOfMotion(pan_angle=0, tilt_angle=0)
        target_point = PointOfMotion(pan_angle=21, tilt_angle=6)

        controller.add_point(current_point)
        controller.add_point(target_point)

        # gimbal still moves with target speed according to the speed manager
        assert rotate_speed_manager.current_speed == 60
        assert tilt_speed_manager.current_speed == 12
        # first point is reached
        gimbal.get_angles = get_zero_angles
        controller.update(camera_speeds)
        assert controller.current_point() == target_point
        assert gimbal.get_angles.call_count == 1
        # Gimbal stopped by itself, when it reached the last point.
        # The speed managers don't know that. Hence, the current speed
        # has to be set to zero and then updated.
        assert rotate_speed_manager.current_speed == 30
        assert tilt_speed_manager.current_speed == 6
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=rotate_speed_manager.current_speed,
            yaw_angle=target_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=tilt_speed_manager.current_speed,
            pitch_angle=target_point.tilt_angle)
