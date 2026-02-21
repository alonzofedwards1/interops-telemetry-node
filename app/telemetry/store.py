import logging
from threading import Lock
from typing import List
from datetime import datetime, timezone

from psycopg2.extras import Json

from app.db.connection import get_connection
from .models import TelemetryEvent

logger = logging.getLogger(__name__)


class TelemetryStore:
    """
    Thread-safe singleton telemetry buffer.

    - Buffers telemetry events in memory
    - Can flush to PostgreSQL
    - Contains ONLY business-level telemetry
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._events = []
                cls._instance._events_lock = Lock()
            return cls._instance

    # ---------------------------
    # In-Memory Buffer
    # ---------------------------

    def add(self, event: TelemetryEvent) -> None:
        """
        Add a business telemetry event to memory buffer.
        """
        try:
            with self._events_lock:
                self._events.append(event)
        except Exception:
            logger.exception("Failed to add telemetry event")

    def get_all(self) -> List[TelemetryEvent]:
        """
        Return copy of all buffered events.
        """
        try:
            with self._events_lock:
                return list(self._events)
        except Exception:
            logger.exception("Failed to retrieve telemetry events")
            return []

    def clear(self) -> None:
        """
        Clear in-memory buffer.
        """
        try:
            with self._events_lock:
                self._events.clear()
        except Exception:
            logger.exception("Failed to clear telemetry store")

    # ---------------------------
    # Database Persistence
    # ---------------------------

    def flush_to_db(self) -> None:
        """
        Persist buffered telemetry events to PostgreSQL.
        """

        events_to_flush: List[TelemetryEvent] = []

        # Extract and clear buffer atomically
        with self._events_lock:
            if not self._events:
                return
            events_to_flush = list(self._events)
            self._events.clear()

        conn = get_connection()

        try:
            with conn.cursor() as cur:
                for event in events_to_flush:
                    cur.execute(
                        """
                        INSERT INTO telemetry_events (
                            event_id,
                            event_type,
                            event_layer,
                            timestamp_utc,
                            source_channel_id,
                            status,
                            duration_ms,
                            correlation_request_id,
                            raw_payload
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            event.event_id,
                            event.event_type,
                            event.event_layer,
                            event.timestamp_utc
                                or datetime.now(timezone.utc),
                            event.source_channel_id,
                            event.status,
                            event.duration_ms,
                            event.correlation_request_id,
                            Json(event.raw_payload or {}),
                        ),
                    )

            conn.commit()

            logger.info(
                "Flushed %d telemetry events to database",
                len(events_to_flush),
            )

        except Exception:
            logger.exception("Failed flushing telemetry events to DB")

            # Put events back into memory if DB write fails
            with self._events_lock:
                self._events.extend(events_to_flush)

        finally:
            conn.close()


def get_store() -> TelemetryStore:
    return TelemetryStore()