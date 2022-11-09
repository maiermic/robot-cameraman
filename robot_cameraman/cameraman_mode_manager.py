import logging
from logging import Logger
from threading import RLock
from typing import Optional

from robot_cameraman.box import Box
from robot_cameraman.camera_controller import CameraController, \
    CameraAngleLimitController, CameraZoomLimitController
from robot_cameraman.events import Event, EventEmitter
from robot_cameraman.gimbal import Gimbal, convert_simple_bgc_angles
from robot_cameraman.tracking import TrackingStrategy, AlignTrackingStrategy, \
    SearchTargetStrategy, StaticSearchTargetStrategy
from robot_cameraman.camera_speeds import ZoomSpeed, CameraSpeeds
from simplebgc.gimbal import ControlMode

logger: Logger = logging.getLogger(__name__)


class CameramanModeManager:

    def __init__(
            self,
            camera_controller: CameraController,
            camera_zoom_limit_controller: CameraZoomLimitController,
            camera_angle_limit_controller: CameraAngleLimitController,
            align_tracking_strategy: AlignTrackingStrategy,
            tracking_strategy: TrackingStrategy,
            search_target_strategy: SearchTargetStrategy,
            gimbal: Gimbal,
            event_emitter: EventEmitter) -> None:
        self._event_emitter = event_emitter
        self._camera_controller = camera_controller
        self._camera_zoom_limit_controller = camera_zoom_limit_controller
        self._camera_angle_limit_controller = camera_angle_limit_controller
        self._align_tracking_strategy = align_tracking_strategy
        self._tracking_strategy = tracking_strategy
        self._search_target_strategy = search_target_strategy
        self._gimbal = gimbal
        self._camera_speeds: CameraSpeeds = CameraSpeeds()
        self._mode_name_lock = RLock()
        self._mode_name = None
        self.mode_name = 'manual'
        # TODO searching does not start if used as initial mode, since current
        #  angles have not been set on StaticSearchTargetStrategy yet
        # self.mode_name = 'searching'
        self.is_zoom_enabled = True
        self.are_limits_applied_in_manual_mode = False

    @property
    def mode_name(self) -> str:
        with self._mode_name_lock:
            return self._mode_name

    @mode_name.setter
    def mode_name(self, new_mode_name: str):
        with self._mode_name_lock:
            previous_mode_name = self._mode_name
            self._mode_name = new_mode_name
            # TODO decouple: introduce listeners to changes
            #   CameramanModeManager should not need to know that
            #   StaticSearchTargetStrategy is called.
            if (previous_mode_name != new_mode_name
                    and isinstance(self._search_target_strategy,
                                   StaticSearchTargetStrategy)):
                if new_mode_name == 'searching':
                    self._search_target_strategy.start()
                if previous_mode_name == 'searching':
                    self._search_target_strategy.stop()

    def update(self, target: Optional[Box], is_target_lost: bool) -> None:
        # check calling convention: target can not be lost if it exists
        assert target is not None or is_target_lost
        self._read_gimbal_angles()
        if self.mode_name not in ['manual', 'angle']:
            if target is None and is_target_lost:
                if self.mode_name == 'aligning':
                    self._camera_speeds.reset()
                self.mode_name = 'searching'
                self._search_target_strategy.update(self._camera_speeds)
            elif (self.mode_name in ['searching', 'aligning']
                  and target is not None
                  and not self._align_tracking_strategy.is_aligned(target)):
                self.mode_name = 'aligning'
                self._align_tracking_strategy.update(
                    self._camera_speeds, target, is_target_lost)
            else:
                self.mode_name = 'tracking'
                self._tracking_strategy.update(self._camera_speeds, target,
                                               is_target_lost)
        if self.mode_name != 'angle':
            if not self.is_zoom_enabled and self.mode_name != 'manual':
                self._camera_speeds.zoom_speed = ZoomSpeed.ZOOM_STOPPED
            if (self.mode_name != 'manual'
                    or self.are_limits_applied_in_manual_mode):
                self._camera_zoom_limit_controller.update(self._camera_speeds)
                self._camera_angle_limit_controller.update(self._camera_speeds)
            self._camera_controller.update(self._camera_speeds)

    def _read_gimbal_angles(self):
        # TODO convert angles in gimbal
        self._event_emitter.emit(
            Event.ANGLES,
            convert_simple_bgc_angles(self._gimbal.get_angles()))

    def start(self):
        self._camera_controller.start()

    def stop(self) -> None:
        """
        Slow down camera till it stops. Call this method only if the update
        method is not called in the meantime by another thread. Otherwise, it
        might interfere with stopping the camera.
        :return:
        """
        logger.debug('Stop camera mode manager')
        self._camera_speeds.reset()
        self._camera_controller.stop(self._camera_speeds)

    def stop_camera(self) -> None:
        """
        Stop camera movement by resetting the camera speeds. Call this method if
        you are not the thread that is controlling the camera. Only one thread
        should call the update method to avoid conflicts.
        :return:
        """
        logger.debug('Stop camera')
        self._camera_speeds.reset()

    def tracking_mode(self) -> None:
        # search target to track
        self.mode_name = 'searching'

    def manual_mode(self) -> None:
        self.mode_name = 'manual'

    def manual_rotate(self, pan_speed: float) -> None:
        self._camera_speeds.pan_speed = pan_speed

    def manual_tilt(self, tilt_speed: float) -> None:
        self._camera_speeds.tilt_speed = tilt_speed

    def manual_zoom(self, zoom_speed: ZoomSpeed) -> None:
        self._camera_speeds.zoom_speed = zoom_speed

    def is_manual_mode(self):
        return self.mode_name == 'manual'

    def angle(self, pan_angle: int, tilt_angle: int) -> None:
        self.mode_name = 'angle'
        self._gimbal.control(
            yaw_mode=ControlMode.angle, yaw_speed=100, yaw_angle=pan_angle,
            pitch_mode=ControlMode.angle, pitch_speed=100,
            pitch_angle=tilt_angle)
