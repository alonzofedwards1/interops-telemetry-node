import sqlite3
import uuid
import json
import os
from datetime import datetime, timedelta, UTC

from app.telemetry.models import TelemetryEvent
from app.pd.materializer import materialize_pd_execution

# --------------------------------------------------
# 🔒 HARD-CODED DB PATH (ABSOLUTE TRUTH)
# --------------------------------------------------
DB_PATH = r"C:\Users\alonz\Documents\interops-telemetry-api\app\db\telemetry.db"

print("Using database:", DB_PATH)

if not os.path.exists(DB_PATH):
    raise FileNotFoundError(f"DB not found: {DB_PATH}")

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def iso_now(offset_ms: int = 0) -> str:
    return (
        datetime.now(UTC) + timedelta(milliseconds=offset_ms)
    ).isoformat().replace("+00:00", "Z")


def insert_event(conn: sqlite3.Connection, event: TelemetryEvent, raw_payload: dict):
    """
    Insert a telemetry event.
    MUST commit before calling materializer to avoid SQLite lock.
    """
    conn.execute(
        """
        INSERT INTO telemetry_events (
            event_id,
            event_type,
            timestamp_utc,
            source_channel_id,
            source_environment,
            status,
            duration_ms,
            correlation_request_id,
            raw_payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.eventId,
            event.eventType,
            event.timestamp,
            event.source.channelId if event.source else None,
            event.source.environment if event.source else None,
            event.outcome.status if event.outcome else None,
            event.outcome.durationMs if event.outcome else None,
            event.correlation.requestId if event.correlation else None,
            json.dumps(raw_payload),  # ✅ SQLite-safe
        ),
    )


# --------------------------------------------------
# Main seeding logic
# --------------------------------------------------
def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    total = 0

    def make_event(status: str | None, materialize: bool):
        nonlocal total

        req_id = f"req-{uuid.uuid4().hex[:8]}"
        evt_id = f"evt-{uuid.uuid4().hex[:8]}"

        payload = {
            "eventId": evt_id,
            "eventType": "pd.request.complete" if materialize else "pd.request.started",
            "timestamp": iso_now(),
            "source": {
                "channelId": "mirth-pd-01",
                "environment": "Test",
            },
            "outcome": {
                "status": status,
                "durationMs": 400,
            } if status else None,
            "correlation": {
                "requestId": req_id,
            },
        }

        event = TelemetryEvent(**payload)

        # 1️⃣ Insert telemetry event (SINGLE WRITER)
        insert_event(conn, event, payload)

        # 2️⃣ COMMIT to release SQLite write lock
        conn.commit()

        # 3️⃣ Materialize PD execution (SAFE – new connection)
        if materialize:
            materialize_pd_execution(event)

        total += 1

    # --------------------------------------------------
    # Seed Data (47 total)
    # --------------------------------------------------

    # 10 SUCCESS → executions
    for _ in range(10):
        make_event("SUCCESS", materialize=True)

    # 25 ERROR → executions
    for _ in range(25):
        make_event("ERROR", materialize=True)

    # 12 STARTED ONLY → ignored
    for _ in range(12):
        make_event(None, materialize=False)

    conn.close()

    print(f"✅ Seed complete: {total} telemetry events inserted")


if __name__ == "__main__":
    seed()
