from unittest.mock import Mock

import pytest

from robot_cameraman.camera_controller import \
    BaseCamPathOfMotionCameraController, PointOfMotion, SpeedManager, \
    ElapsedTime, CameraState, PointOfMotionTargetSpeedCalculator, \
    is_current_point_reached, is_angle_between, CameraAngleLimitController
from robot_cameraman.camera_speeds import CameraSpeeds
from robot_cameraman.gimbal import Angles
from simplebgc.commands import GetAnglesInCmd
from simplebgc.gimbal import Gimbal, ControlMode
from simplebgc.units import from_degree, from_degree_per_sec


def get_angles_in_cmd(pan_angle: float, pan_speed: float,
                      tilt_angle: float, tilt_speed: float):
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
    def max_pan_speed(self):
        return 60

    @pytest.fixture()
    def max_tilt_speed(self):
        return 12

    @pytest.fixture()
    def max_speeds(self, max_pan_speed, max_tilt_speed):
        return CameraSpeeds(pan_speed=max_pan_speed, tilt_speed=max_tilt_speed)

    @pytest.fixture()
    def target_speed_calculator(self):
        return Mock(spec=PointOfMotionTargetSpeedCalculator())

    @pytest.fixture()
    def rotate_speed_manager(self):
        return create_speed_manager_mock()

    @pytest.fixture()
    def tilt_speed_manager(self):
        return create_speed_manager_mock()

    @pytest.fixture()
    def controller(self, gimbal, rotate_speed_manager, tilt_speed_manager,
                   target_speed_calculator):
        return BaseCamPathOfMotionCameraController(
            gimbal, rotate_speed_manager, tilt_speed_manager,
            target_speed_calculator)

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

    def test_empty_path_has_no_points(self, controller):
        assert not controller.has_points()

    def test_empty_path_has_not_next_points(self, controller):
        assert not controller.has_next_point()

    def test_end_of_empty_path_is_reached(self, controller):
        assert controller.is_end_of_path_reached()

    def test_end_of_single_point_path_is_not_reached(
            self, controller, gimbal, get_zero_angles, non_zero_point,
            camera_speeds, target_speed_calculator, max_speeds):
        gimbal.get_angles = should_not_be_called_mock('gimbal.get_angles')
        target_speed_calculator.calculate = Mock(return_value=max_speeds)
        controller.add_point(non_zero_point)
        controller.start()
        assert not controller.is_end_of_path_reached()
        gimbal.get_angles = get_zero_angles
        controller.update(camera_speeds)
        assert not controller.is_end_of_path_reached()

    def test_end_of_single_point_path_is_reached(
            self, controller, gimbal, get_zero_angles, zero_point,
            camera_speeds, target_speed_calculator, max_speeds):
        gimbal.get_angles = should_not_be_called_mock('gimbal.get_angles')
        target_speed_calculator.calculate = Mock(return_value=max_speeds)
        controller.add_point(zero_point)
        controller.start()
        assert not controller.is_end_of_path_reached()
        gimbal.get_angles = get_zero_angles
        controller.update(camera_speeds)
        assert controller.is_end_of_path_reached()

    def test_end_of_multi_point_path_is_reached(
            self, controller, gimbal, get_zero_angles, zero_point,
            non_zero_point, camera_speeds, max_speeds, target_speed_calculator):
        gimbal.get_angles = should_not_be_called_mock('gimbal.get_angles')
        controller.add_point(zero_point)
        controller.add_point(non_zero_point)
        controller.start()
        assert not controller.is_end_of_path_reached()
        gimbal.get_angles = get_zero_angles
        target_speed_calculator.calculate = Mock(return_value=max_speeds)

        controller.update(camera_speeds)
        assert not controller.is_end_of_path_reached()
        assert controller.current_point() == non_zero_point
        # still at the same angle as before, i.e. end not reached yet
        controller.update(camera_speeds)
        assert not controller.is_end_of_path_reached()
        # angle of last point is reached
        gimbal.get_angles = Mock(
            return_value=get_angles_in_cmd(
                pan_angle=int(non_zero_point.pan_angle), pan_speed=0,
                tilt_angle=int(non_zero_point.tilt_angle), tilt_speed=0))
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
            get_zero_angles, rotate_speed_manager, tilt_speed_manager,
            target_speed_calculator, max_speeds):
        gimbal.get_angles = get_zero_angles
        gimbal.control = Mock()
        target_speed_calculator.calculate = Mock(return_value=max_speeds)
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
            non_zero_point, rotate_speed_manager, tilt_speed_manager,
            target_speed_calculator, max_speeds):
        gimbal.get_angles = get_zero_angles
        gimbal.control = Mock()
        target_speed_calculator.calculate = Mock(return_value=max_speeds)
        controller.add_point(non_zero_point)

        controller.start()
        assert gimbal.get_angles.call_count == 0
        assert gimbal.control.call_count == 0

        assert rotate_speed_manager.current_speed == 0
        assert tilt_speed_manager.current_speed == 0
        assert rotate_speed_manager.acceleration_per_second == 0
        assert tilt_speed_manager.acceleration_per_second == 0
        rotate_speed_manager.target_speed = 60
        tilt_speed_manager.target_speed = 12
        # should move with minimum speed to first point,
        # since current speed and acceleration are zero
        controller.update(camera_speeds)
        assert gimbal.get_angles.call_count == 1
        min_speed = 1
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle, yaw_speed=min_speed,
            yaw_angle=non_zero_point.pan_angle,
            pitch_mode=ControlMode.angle, pitch_speed=min_speed,
            pitch_angle=non_zero_point.tilt_angle)
        assert camera_speeds == CameraSpeeds()

    def test_move_with_increasing_speed_to_point(
            self, controller, camera_speeds, gimbal,
            get_zero_angles, zero_point,
            rotate_speed_manager, tilt_speed_manager, target_speed_calculator):
        gimbal.get_angles = get_zero_angles
        gimbal.control = Mock()
        rotate_speed_manager.acceleration_per_second = 4
        tilt_speed_manager.acceleration_per_second = 1
        current_point = PointOfMotion(pan_angle=21, tilt_angle=6, time=3)
        next_point = PointOfMotion(pan_angle=0, pan_clockwise=False,
                                   tilt_angle=0, tilt_clockwise=False, time=3)

        controller.add_point(current_point)
        controller.add_point(next_point)

        controller.start()
        assert gimbal.get_angles.call_count == 0
        assert gimbal.control.call_count == 0

        # Gimbal is not moving
        assert rotate_speed_manager.current_speed == 0
        assert tilt_speed_manager.current_speed == 0
        # assert rotate_speed_manager.target_speed == 0
        # assert tilt_speed_manager.target_speed == 0
        # First point is not reached yet
        gimbal.get_angles = get_zero_angles
        camera_state = CameraState(speeds=camera_speeds,
                                   pan_angle=zero_point.pan_angle,
                                   tilt_angle=zero_point.tilt_angle)
        # New target speeds are calculated based on next point of motion.
        # Gimbal has to pan 7°/s to get in 3s from 21° to 0°.
        # Gimbal has to tilt 2°/s to get in 3s from 6° to 0°.
        target_speeds = CameraSpeeds(pan_speed=7, tilt_speed=2)
        target_speed_calculator.calculate = Mock(return_value=target_speeds)
        # TODO assert target speeds have been set before calculate is called

        # should move with speeds of speed managers to first point
        controller.update(camera_speeds)
        # calculator has been used to calculate target speeds
        target_speed_calculator.calculate.assert_called_once_with(
            camera_state, current_point)
        # and target speeds have been set on speed managers
        assert rotate_speed_manager.target_speed == target_speeds.pan_speed
        assert tilt_speed_manager.target_speed == target_speeds.tilt_speed
        assert rotate_speed_manager.current_speed == 4
        assert tilt_speed_manager.current_speed == 1
        assert gimbal.get_angles.call_count == 1
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=rotate_speed_manager.current_speed,
            yaw_angle=current_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=tilt_speed_manager.current_speed,
            pitch_angle=current_point.tilt_angle)
        assert not controller.is_target_speed_reached()

        gimbal.get_angles = Mock(
            return_value=get_angles_in_cmd(pan_angle=7, pan_speed=4,
                                           tilt_angle=2, tilt_speed=1))
        gimbal.control.reset_mock()
        # should increase speeds till target speeds are reached
        controller.update(camera_speeds)
        assert gimbal.get_angles.call_count == 1
        # Should not have been called again, since target didn't change.
        assert target_speed_calculator.calculate.call_count == 1
        # Target speeds are reached
        assert rotate_speed_manager.current_speed == 7
        assert tilt_speed_manager.current_speed == 2
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
        # Should not have been called again, since target didn't change.
        assert target_speed_calculator.calculate.call_count == 1
        # Target speed already reached => no control command needs to be sent
        assert gimbal.control.call_count == 0
        # but time of speed managers has to be updated
        assert (rotate_speed_manager.update.call_count == 1
                or rotate_speed_manager.reset.call_count == 1)
        assert (tilt_speed_manager.update.call_count == 1
                or tilt_speed_manager.reset.call_count == 1)
        assert controller.current_point() == current_point

    def test_move_to_next_point_when_current_point_is_reached(
            self, controller, camera_speeds, gimbal, get_zero_angles,
            rotate_speed_manager, tilt_speed_manager, target_speed_calculator,
            max_speeds):
        gimbal.control = Mock()
        rotate_speed_manager.acceleration_per_second = 4
        rotate_speed_manager.target_speed = 60
        rotate_speed_manager.current_speed = rotate_speed_manager.target_speed
        tilt_speed_manager.acceleration_per_second = 1
        tilt_speed_manager.target_speed = 12
        tilt_speed_manager.current_speed = tilt_speed_manager.target_speed
        current_point = PointOfMotion(pan_angle=0, pan_clockwise=False,
                                      tilt_angle=0, tilt_clockwise=False)
        target_point = PointOfMotion(pan_angle=21, tilt_angle=6, time=3)

        controller.add_point(current_point)
        controller.add_point(target_point)
        controller.start()

        # gimbal is already moving
        gimbal.get_angles = Mock(
            return_value=get_angles_in_cmd(pan_angle=1, pan_speed=60,
                                           tilt_angle=1, tilt_speed=12))
        target_speed_calculator.calculate = Mock(return_value=max_speeds)
        # and should move to first point
        controller.update(camera_speeds)
        gimbal.control.reset_mock()

        # Gimbal still moves with target speed according to the speed manager
        assert rotate_speed_manager.current_speed == 60
        assert tilt_speed_manager.current_speed == 12
        # Old target speeds used to move to first point
        assert rotate_speed_manager.target_speed == 60
        assert tilt_speed_manager.target_speed == 12
        # First point is reached
        gimbal.get_angles = get_zero_angles
        camera_state = CameraState(speeds=camera_speeds,
                                   pan_angle=current_point.pan_angle,
                                   tilt_angle=current_point.tilt_angle)
        # New target speeds are calculated based on next point of motion.
        # Gimbal has to pan 7°/s to get in 3s from 0° to 21°.
        # Gimbal has to tilt 2°/s to get in 3s from 0° to 6°.
        target_speeds = CameraSpeeds(pan_speed=7, tilt_speed=2)
        target_speed_calculator.calculate = Mock(return_value=target_speeds)
        # TODO assert target speeds have been set before calculate is called

        controller.update(camera_speeds)
        assert controller.current_point() == target_point
        assert gimbal.get_angles.call_count == 1
        # calculator has been used to calculate target speeds
        target_speed_calculator.calculate.assert_called_once_with(
            camera_state, target_point)
        # and target speeds have been set on speed managers
        assert rotate_speed_manager.target_speed == target_speeds.pan_speed
        assert tilt_speed_manager.target_speed == target_speeds.tilt_speed
        # Gimbal stopped by itself, when it reached the last point.
        # The speed managers don't know that. Hence, the current speed
        # has to be set to zero and then updated.
        assert rotate_speed_manager.current_speed == 4
        assert tilt_speed_manager.current_speed == 1
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=rotate_speed_manager.current_speed,
            yaw_angle=target_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=tilt_speed_manager.current_speed,
            pitch_angle=target_point.tilt_angle)

    def test_target_speeds_are_calculated_before_current_speeds_are_updated(
            self, controller, camera_speeds, gimbal, get_zero_angles,
            rotate_speed_manager, tilt_speed_manager, target_speed_calculator,
            max_speeds):
        rotate_speed_manager.acceleration_per_second = 2
        tilt_speed_manager.acceleration_per_second = 1

        first_point = PointOfMotion(pan_angle=0, pan_clockwise=False,
                                    tilt_angle=0, tilt_clockwise=False)
        last_point = PointOfMotion(pan_angle=21, tilt_angle=6, time=3)

        controller.add_point(first_point)
        controller.add_point(last_point)
        controller.start()

        # gimbal is not at first point yet
        gimbal.get_angles = Mock(
            return_value=get_angles_in_cmd(pan_angle=180, pan_speed=60,
                                           tilt_angle=90, tilt_speed=12))
        camera_speeds.pan_speed = 60
        camera_speeds.tilt_speed = 12
        camera_state = CameraState(speeds=camera_speeds, pan_angle=180,
                                   tilt_angle=90)
        # gimbal should move with maximum speed to first point
        target_speed_calculator.calculate = Mock(return_value=max_speeds)
        # Assert that target speeds are set on speed manager before updating
        # current speeds. Save update-method, replace it with assertion that
        # calls saved update-method.
        update_rotate_speed_manager = rotate_speed_manager.update
        update_tilt_speed_manager = tilt_speed_manager.update

        def assert_update_rotate_speed_manager():
            assert rotate_speed_manager.target_speed == max_speeds.pan_speed, \
                'target pan speed has to be set before updating current speed'
            return update_rotate_speed_manager()

        def assert_update_tilt_speed_manager():
            assert tilt_speed_manager.target_speed == max_speeds.tilt_speed, \
                'target tilt speed has to be set before updating current speed'
            return update_tilt_speed_manager()

        rotate_speed_manager.update = Mock(
            side_effect=assert_update_rotate_speed_manager)
        tilt_speed_manager.update = Mock(
            side_effect=assert_update_tilt_speed_manager)
        # TODO pass camera state to update (do not get angles in controller)
        controller.update(camera_speeds)
        # calculator has been used to calculate target speeds
        target_speed_calculator.calculate.assert_called_once_with(
            camera_state, first_point)
        # and target speeds have been set on speed managers
        assert rotate_speed_manager.target_speed == max_speeds.pan_speed
        assert tilt_speed_manager.target_speed == max_speeds.tilt_speed
        # and then current speeds have been updated
        rotate_speed_manager.update.assert_called_once()
        tilt_speed_manager.update.assert_called_once()
        # and used to control the gimbal
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=2,
            yaw_angle=first_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=1,
            pitch_angle=first_point.tilt_angle)

    def test_no_stop_at_intermediate_point_if_next_point_is_in_same_direction(
            self, controller, camera_speeds, gimbal, get_zero_angles,
            zero_point,
            rotate_speed_manager, tilt_speed_manager, target_speed_calculator,
            max_speeds, max_pan_speed, max_tilt_speed):
        gimbal.control = Mock()
        target_speed_calculator.calculate = Mock(return_value=max_speeds)
        rotate_speed_manager.acceleration_per_second = max_pan_speed / 2
        tilt_speed_manager.acceleration_per_second = max_tilt_speed / 2

        first_point = zero_point
        second_point = PointOfMotion(pan_angle=100, tilt_angle=20, time=2)
        controller.add_point(first_point)
        controller.add_point(second_point)
        controller.start()

        gimbal.get_angles = Mock(
            return_value=get_angles_in_cmd(pan_angle=300, pan_speed=0,
                                           tilt_angle=354, tilt_speed=0))
        controller.update(camera_speeds)
        # Tell gimbal to move with the speed of the first point to the second
        # point.
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=max_pan_speed / 2,
            yaw_angle=second_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=max_tilt_speed / 2,
            pitch_angle=second_point.tilt_angle)
        gimbal.control.reset_mock()

        assert rotate_speed_manager.current_speed < rotate_speed_manager.target_speed
        assert tilt_speed_manager.current_speed < tilt_speed_manager.target_speed
        # increase speed
        controller.update(camera_speeds)
        # Tell gimbal to move with the speed of the first point to the second
        # point.
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=max_pan_speed,
            yaw_angle=second_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=max_tilt_speed,
            pitch_angle=second_point.tilt_angle)
        gimbal.control.reset_mock()

        # First point is reached
        gimbal.get_angles = get_zero_angles
        # Continue moving to the second point, but with the speed of the second
        # point, i.e. speed has to be decreased from max speed to:
        # - pan 50°/s to get in 2s from 0° to 100°
        # - tilt 10°/s to get in 2s from 0° to 20°
        target_speed_calculator.calculate = Mock(
            return_value=CameraSpeeds(pan_speed=50, tilt_speed=10))
        controller.update(camera_speeds)
        target_speed_calculator.calculate.assert_called_once_with(
            CameraState(speeds=camera_speeds,
                        pan_angle=first_point.pan_angle,
                        tilt_angle=first_point.tilt_angle),
            second_point)
        gimbal.control.assert_called_once_with(
            yaw_mode=ControlMode.angle,
            yaw_speed=50,
            yaw_angle=second_point.pan_angle,
            pitch_mode=ControlMode.angle,
            pitch_speed=10,
            pitch_angle=second_point.tilt_angle)


class TestPointOfMotionTargetSpeedCalculator:
    @pytest.fixture()
    def max_pan_speed(self):
        return 60

    @pytest.fixture()
    def max_tilt_speed(self):
        return 12

    @pytest.fixture()
    def calculator(self, max_pan_speed, max_tilt_speed):
        return PointOfMotionTargetSpeedCalculator(max_pan_speed=max_pan_speed,
                                                  max_tilt_speed=max_tilt_speed)

    def test_get_degree_per_second(self, calculator):
        # gimbal has to move 2°/s clockwise to get in 3s from 0° to 6°
        assert 2 == calculator.get_degree_per_second(
            current_angle=0, target_angle=6, clockwise=True, travel_time=3)
        # gimbal has to move 2°/s counter clockwise to get in 3s from 6° to 0°
        assert 2 == calculator.get_degree_per_second(
            current_angle=6, target_angle=0, clockwise=False, travel_time=3)

    def test_calculate_returns_max_speeds_when_time_is_zero(
            self, calculator, max_pan_speed, max_tilt_speed):
        target_speeds = calculator.calculate(
            state=CameraState(speeds=Mock(), pan_angle=0, tilt_angle=0),
            target=PointOfMotion(pan_angle=180, tilt_angle=90, time=0))
        assert max_pan_speed == target_speeds.pan_speed
        assert max_tilt_speed == target_speeds.tilt_speed

    def test_calculate(self, calculator):
        target_speeds = calculator.calculate(
            state=CameraState(speeds=Mock(), pan_angle=0, tilt_angle=0),
            target=PointOfMotion(pan_angle=180, tilt_angle=90, time=9))
        # gimbal has to pan 20°/s to get in 9s from 0° to 180°
        assert 20 == target_speeds.pan_speed
        # gimbal has to tilt 10°/s to get in 9s from 0° to 90°
        assert 10 == target_speeds.tilt_speed

    def test_calculate_overstep_360(self, calculator):
        target_speeds = calculator.calculate(
            state=CameraState(speeds=Mock(), pan_angle=280, tilt_angle=320),
            target=PointOfMotion(pan_angle=10, tilt_angle=20, time=6))
        # gimbal has to pan 15°/s counter-clockwise to get
        # in 6s from 280° to 10° (90° difference)
        assert 15 == target_speeds.pan_speed
        # gimbal has to tilt 10°/s counter-clockwise to get
        # in 6s from 320° to 20° (60° difference)
        assert 10 == target_speeds.tilt_speed

    def test_calculate_counter_clockwise(self, calculator):
        target_speeds = calculator.calculate(
            state=CameraState(speeds=Mock(), pan_angle=100, tilt_angle=80),
            target=PointOfMotion(pan_angle=10, pan_clockwise=False,
                                 tilt_angle=20, tilt_clockwise=False, time=6))
        # gimbal has to pan 15°/s counter-clockwise to get
        # in 6s from 100° to 10° (90° difference)
        assert 15 == target_speeds.pan_speed
        # gimbal has to tilt 10°/s counter-clockwise to get
        # in 6s from 80° to 20° (60° difference)
        assert 10 == target_speeds.tilt_speed

    def test_calculate_counter_clockwise_overstep_360(self, calculator):
        target_speeds = calculator.calculate(
            state=CameraState(speeds=Mock(), pan_angle=10, tilt_angle=20),
            target=PointOfMotion(pan_angle=280, pan_clockwise=False,
                                 tilt_angle=320, tilt_clockwise=False, time=6))
        # gimbal has to pan 15°/s counter-clockwise to get
        # in 6s from 10° to 280° (90° difference)
        assert 15 == target_speeds.pan_speed
        # gimbal has to tilt 10°/s counter-clockwise to get
        # in 6s from 20° to 320° (60° difference)
        assert 10 == target_speeds.tilt_speed

    def test_calculate_respects_max_speed(
            self, calculator, max_pan_speed, max_tilt_speed):
        target_speeds = calculator.calculate(
            state=CameraState(speeds=Mock(), pan_angle=0, tilt_angle=0),
            target=PointOfMotion(pan_angle=180, tilt_angle=90, time=1))
        assert max_pan_speed == target_speeds.pan_speed
        assert max_tilt_speed == target_speeds.tilt_speed


class TestIsCurrentPointReached:
    @pytest.fixture()
    def zero_point(self):
        return PointOfMotion(pan_angle=0, tilt_angle=0)

    def test_current_point_is_reached_if_close(self):
        c = PointOfMotion(pan_angle=180, pan_clockwise=True,
                          tilt_angle=30, tilt_clockwise=True)
        n = PointOfMotion(pan_angle=270, pan_clockwise=True,
                          tilt_angle=15, tilt_clockwise=False)
        assert is_current_point_reached(pan_angle=179.96, tilt_angle=30.04,
                                        current_target=c, next_target=n)
        assert is_current_point_reached(pan_angle=179.96, tilt_angle=30.04,
                                        current_target=c, next_target=None)

    def test_current_point_is_reached_if_close_with_overstep_360(
            self, zero_point):
        assert is_current_point_reached(
            pan_angle=359.99, tilt_angle=359.96,
            current_target=zero_point,
            next_target=PointOfMotion(pan_angle=100, tilt_angle=20, time=2))

    def test_current_point_is_not_reached_if_not_close_with_overstep_360(
            self, zero_point):
        assert not is_current_point_reached(
            pan_angle=300, tilt_angle=354,
            current_target=zero_point,
            next_target=PointOfMotion(pan_angle=100, tilt_angle=20, time=2))

    def test_current_point_is_reached_if_close_with_counter_clockwise_overstep_360(
            self, zero_point):
        assert is_current_point_reached(
            pan_angle=0, tilt_angle=0,
            current_target=PointOfMotion(
                pan_angle=359.99, pan_clockwise=False,
                tilt_angle=359.99, tilt_clockwise=False),
            next_target=zero_point)

    def test_current_point_is_not_reached_if_not_close_with_counter_clockwise_overstep_360(
            self, zero_point):
        assert not is_current_point_reached(
            pan_angle=300, tilt_angle=354,
            current_target=PointOfMotion(
                pan_angle=359.99, pan_clockwise=False,
                tilt_angle=359.99, tilt_clockwise=False),
            next_target=zero_point)

    def test_current_point_is_not_reached_if_only_one_is_close(self):
        c = PointOfMotion(pan_angle=180, pan_clockwise=True,
                          tilt_angle=30, tilt_clockwise=True)
        n = PointOfMotion(pan_angle=270, pan_clockwise=True,
                          tilt_angle=15, tilt_clockwise=False)
        # tilt angle is reached before pan angle is reached
        assert not is_current_point_reached(pan_angle=179.91, tilt_angle=30.04,
                                            current_target=c, next_target=n)
        # pan angle is reached before tilt angle is reached
        assert not is_current_point_reached(pan_angle=179.96, tilt_angle=29.91,
                                            current_target=c, next_target=n)

    def test_current_point_is_reached_if_one_is_close_after_the_other(self):
        c = PointOfMotion(pan_angle=180, pan_clockwise=True,
                          tilt_angle=30, tilt_clockwise=True)
        n = PointOfMotion(pan_angle=270, pan_clockwise=True,
                          tilt_angle=45, tilt_clockwise=True)
        # If the next point is in the same direction as the current point,
        # there is no stop at the intermediate point.

        # Tilt angle has been reached before pan angle is reached,
        # but tilting did not stop and tilt angle is not close anymore.
        assert is_current_point_reached(pan_angle=179.96, tilt_angle=30.14,
                                        current_target=c, next_target=n)
        # Pan angle has been reached before tilt angle is reached,
        # but panning did not stop and pan angle is not close anymore.
        assert is_current_point_reached(pan_angle=180.14, tilt_angle=29.96,
                                        current_target=c, next_target=n)


class TestIsAngleBetween:
    def test_is_angle_between(self):
        assert is_angle_between(left=0, angle=10, right=20, clockwise=True)
        assert not is_angle_between(left=0, angle=10, right=20, clockwise=False)
        assert is_angle_between(left=0, angle=0, right=0, clockwise=True)
        assert is_angle_between(left=0, angle=0, right=0, clockwise=False)
        assert is_angle_between(left=4.2, angle=4.2, right=4.2, clockwise=True)
        assert is_angle_between(left=4.2, angle=4.2, right=4.2, clockwise=False)

    def test_is_angle_between_clockwise_overstep_360(self):
        assert is_angle_between(left=300, angle=310, right=120, clockwise=True)
        assert is_angle_between(left=300, angle=110, right=120, clockwise=True)
        assert not is_angle_between(
            left=300, angle=180, right=120, clockwise=True)

    def test_is_angle_between_counter_clockwise_overstep_360(self):
        assert is_angle_between(left=120, angle=310, right=300, clockwise=False)
        assert is_angle_between(left=120, angle=110, right=300, clockwise=False)
        assert not is_angle_between(
            left=120, angle=180, right=300, clockwise=False)


class TestCameraAngleLimitController:
    @pytest.fixture()
    def controller(self):
        return CameraAngleLimitController()

    def test_stop_panning_forward_when_max_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=15.1, pan_speed=42,
                   tilt_angle=0, tilt_speed=0))
        camera_speeds = CameraSpeeds(pan_speed=42)
        controller.min_pan_angle = 0
        controller.max_pan_angle = 15.0
        controller.update(camera_speeds)
        assert camera_speeds.pan_speed == 0

    def test_allow_panning_back_when_max_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=15.1, pan_speed=0,
                   tilt_angle=0, tilt_speed=0))
        camera_speeds = CameraSpeeds(pan_speed=-42)
        controller.min_pan_angle = 0
        controller.max_pan_angle = 15.0
        controller.update(camera_speeds)
        assert camera_speeds.pan_speed == -42

    def test_stop_panning_forward_when_min_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=344.9, pan_speed=-42,
                   tilt_angle=0, tilt_speed=0))
        camera_speeds = CameraSpeeds(pan_speed=-42)
        controller.min_pan_angle = 345.0
        controller.max_pan_angle = 0
        controller.update(camera_speeds)
        assert camera_speeds.pan_speed == 0

    def test_allow_panning_back_when_min_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=344.9, pan_speed=0,
                   tilt_angle=0, tilt_speed=0))
        camera_speeds = CameraSpeeds(pan_speed=42)
        controller.min_pan_angle = 345.0
        controller.max_pan_angle = 0
        controller.update(camera_speeds)
        assert camera_speeds.pan_speed == 42

    def test_allow_panning_when_no_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=350, pan_speed=30,
                   tilt_angle=0, tilt_speed=0))
        camera_speeds = CameraSpeeds(pan_speed=42)
        controller.min_pan_angle = 345.0
        controller.max_pan_angle = 0
        controller.update(camera_speeds)
        assert camera_speeds.pan_speed == 42
        controller.update_current_angles(
            Angles(pan_angle=350, pan_speed=-30,
                   tilt_angle=0, tilt_speed=0))
        camera_speeds = CameraSpeeds(pan_speed=-42)
        controller.min_pan_angle = 345.0
        controller.max_pan_angle = 0
        controller.update(camera_speeds)
        assert camera_speeds.pan_speed == -42

    def test_stop_tilting_forward_when_max_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=0, pan_speed=0,
                   tilt_angle=5.1, tilt_speed=42))
        camera_speeds = CameraSpeeds(tilt_speed=42)
        controller.min_tilt_angle = 350.0
        controller.max_tilt_angle = 5.0
        controller.update(camera_speeds)
        assert camera_speeds.tilt_speed == 0

    def test_allow_tilting_back_when_max_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=0, pan_speed=0,
                   tilt_angle=5.1, tilt_speed=0))
        camera_speeds = CameraSpeeds(tilt_speed=-42)
        controller.min_tilt_angle = 350.0
        controller.max_tilt_angle = 5.0
        controller.update(camera_speeds)
        assert camera_speeds.tilt_speed == -42

    def test_stop_tilting_forward_when_min_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=0, pan_speed=0,
                   tilt_angle=349.9, tilt_speed=-42))
        camera_speeds = CameraSpeeds(tilt_speed=-42)
        controller.min_tilt_angle = 350.0
        controller.max_tilt_angle = 5.0
        controller.update(camera_speeds)
        assert camera_speeds.tilt_speed == 0

    def test_allow_tilting_back_when_min_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=0, pan_speed=0,
                   tilt_angle=349.9, tilt_speed=42))
        camera_speeds = CameraSpeeds(tilt_speed=42)
        controller.min_tilt_angle = 350.0
        controller.max_tilt_angle = 5.0
        controller.update(camera_speeds)
        assert camera_speeds.tilt_speed == 42

    def test_allow_tilting_when_no_limit_is_reached(
            self, controller: CameraAngleLimitController):
        controller.update_current_angles(
            Angles(pan_angle=0, pan_speed=0,
                   tilt_angle=1.0, tilt_speed=42))
        camera_speeds = CameraSpeeds(tilt_speed=42)
        controller.min_tilt_angle = 350.0
        controller.max_tilt_angle = 5.0
        controller.update(camera_speeds)
        assert camera_speeds.tilt_speed == 42
        controller.update_current_angles(
            Angles(pan_angle=0, pan_speed=0,
                   tilt_angle=1.0, tilt_speed=-30))
        camera_speeds = CameraSpeeds(tilt_speed=-42)
        controller.min_tilt_angle = 350.0
        controller.max_tilt_angle = 5.0
        controller.update(camera_speeds)
        assert camera_speeds.tilt_speed == -42
