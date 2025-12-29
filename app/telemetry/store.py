import logging
from threading import Lock
from typing import List

from .models import TelemetryEvent

logger = logging.getLogger(__name__)


class TelemetryStore:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._events = []
                cls._instance._events_lock = Lock()
            return cls._instance

    def add(self, event: TelemetryEvent) -> None:
        try:
            with self._events_lock:
                self._events.append(event)
        except Exception:
            logger.exception("Failed to add telemetry event")

    def get_all(self) -> List[TelemetryEvent]:
        try:
            with self._events_lock:
                return list(self._events)
        except Exception:
            logger.exception("Failed to retrieve telemetry events")
            return []

    def clear(self) -> None:
        try:
            with self._events_lock:
                self._events.clear()
        except Exception:
            logger.exception("Failed to clear telemetry store")


def get_store() -> TelemetryStore:
    return TelemetryStore()
