from enum import Enum, auto
from typing import Callable, List, Dict


# TODO use StrEnum after switching to Python 3.11
class Event(Enum):
    ANGLES = auto()
    """Current angles are emitted after they have been read."""
    FOCAL_LENGTH = auto()
    ZOOM_RATIO = auto()
    ZOOM_INDEX = auto()


Listener = Callable


class EventEmitter:
    _listeners: Dict[Event, List[Listener]]

    def __init__(self) -> None:
        self._listeners = dict()

    def add_listener(self, event: Event, listener: Listener):
        listeners = self._get_event_listeners(event)
        listeners.append(listener)

    def _get_event_listeners(self, event: Event):
        return self._listeners.setdefault(event, [])

    def emit(self, event: Event, value):
        property_listeners = self._get_event_listeners(event)
        for listener in property_listeners:
            listener(value)
