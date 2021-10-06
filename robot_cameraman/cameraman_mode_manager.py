import logging
from logging import Logger
from typing import Optional

from robot_cameraman.box import Box
from robot_cameraman.camera_controller import CameraController
from robot_cameraman.tracking import TrackingStrategy, CameraSpeeds, \
    AlignTrackingStrategy, SearchTargetStrategy

logger: Logger = logging.getLogger(__name__)


class CameramanModeManager:

    def __init__(
            self,
            camera_controller: CameraController,
            align_tracking_strategy: AlignTrackingStrategy,
            tracking_strategy: TrackingStrategy,
            search_target_strategy: SearchTargetStrategy) -> None:
        self._camera_controller = camera_controller
        self._align_tracking_strategy = align_tracking_strategy
        self._tracking_strategy = tracking_strategy
        self._search_target_strategy = search_target_strategy
        self._camera_speeds: CameraSpeeds = CameraSpeeds()
        self.mode_name = 'manual'

    def update(self, target: Optional[Box], is_target_lost: bool) -> None:
        # check calling convention: target can not be lost if it exists
        assert target is not None or is_target_lost
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
            self._camera_controller.update(self._camera_speeds)

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

    def manual_rotate(self, pan_speed: int) -> None:
        self._camera_speeds.pan_speed = pan_speed

    def manual_tilt(self, tilt_speed: int) -> None:
        self._camera_speeds.tilt_speed = tilt_speed

    def manual_zoom(self, zoom_speed: int) -> None:
        self._camera_speeds.zoom_speed = zoom_speed

    def is_manual_mode(self):
        return self.mode_name == 'manual'

    def angle(self, pan_angle: int, tilt_angle: int) -> None:
        self.mode_name = 'angle'
        from simplebgc.serial_example import control_gimbal
        control_gimbal(yaw_mode=2, yaw_speed=100, yaw_angle=pan_angle,
                       pitch_mode=2, pitch_speed=100, pitch_angle=tilt_angle)
