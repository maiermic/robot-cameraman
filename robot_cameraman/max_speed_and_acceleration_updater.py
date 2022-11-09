import dataclasses
from typing import Tuple, List, TypeVar, NamedTuple

from robot_cameraman.camera_controller import SpeedManager
from robot_cameraman.tracking import SimpleTrackingStrategy, \
    RotateSearchTargetStrategy
from robot_cameraman.camera_speeds import CameraSpeeds

Updatable = TypeVar(
    'Updatable',
    CameraSpeeds,
    SpeedManager,
    SimpleTrackingStrategy,
    RotateSearchTargetStrategy)


class _UpdateEntry(NamedTuple):
    max_speed: float
    property_name: str
    object: object


# See https://github.com/maiermic/robot-cameraman/issues/13
class MaxSpeedAndAccelerationUpdater:
    # the first value is the max speed at zoom ratio 1.0x
    _camera_speeds: List[Tuple[CameraSpeeds, CameraSpeeds]]
    # the first value is the max acceleration at zoom ratio 1.0x
    _speed_managers: List[Tuple[float, SpeedManager]]
    # the first value is the max speed at zoom ratio 1.0x
    _simple_tracking_strategy: List[Tuple[float, SimpleTrackingStrategy]]
    # the first value is the max speed at zoom ratio 1.0x
    _rotate_search_target_strategy: List[
        Tuple[float, RotateSearchTargetStrategy]]
    # TODO remove lists above and move their entries to _entries
    _entries: List[_UpdateEntry]

    def __init__(self):
        self._camera_speeds = []
        self._speed_managers = []
        self._simple_tracking_strategy = []
        self._rotate_search_target_strategy = []
        self._entries = []

    def add(self, updatable: Updatable) -> Updatable:
        if isinstance(updatable, CameraSpeeds):
            self._camera_speeds.append(
                (dataclasses.replace(updatable), updatable))
        if isinstance(updatable, SpeedManager):
            self._speed_managers.append(
                (updatable.acceleration_per_second, updatable))
        if isinstance(updatable, SimpleTrackingStrategy):
            self._simple_tracking_strategy.append(
                (updatable.max_allowed_speed, updatable))
        if isinstance(updatable, RotateSearchTargetStrategy):
            self._rotate_search_target_strategy.append(
                (updatable.speed, updatable))
        return updatable

    def add_updatable_property(self, obj: object, property_name: str):
        self._entries.append(
            _UpdateEntry(max_speed=getattr(obj, property_name),
                         property_name=property_name,
                         object=obj))

    def add_updatable_properties(self, obj: object, property_names: List[str]):
        for property_name in property_names:
            self.add_updatable_property(obj, property_name)

    def on_zoom_ratio(self, zoom_ratio):
        for max_speeds, camera_speeds in self._camera_speeds:
            camera_speeds.pan_speed = max_speeds.pan_speed / zoom_ratio
            camera_speeds.tilt_speed = max_speeds.tilt_speed / zoom_ratio
        for max_speed, speed_manager in self._speed_managers:
            speed_manager.acceleration_per_second = max_speed / zoom_ratio
        for max_speed, search_strategy in self._simple_tracking_strategy:
            search_strategy.max_allowed_speed = max_speed / zoom_ratio
        for max_speed, search_strategy in self._rotate_search_target_strategy:
            search_strategy.speed = max_speed / zoom_ratio
        for e in self._entries:
            setattr(e.object, e.property_name, e.max_speed / zoom_ratio)
