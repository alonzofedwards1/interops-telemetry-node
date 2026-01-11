import json
import logging
from fastapi import APIRouter, Body, HTTPException

from app.db.connection import get_connection
from app.telemetry.models import TelemetryEvent
from app.telemetry.validator import validate_event_payload
from app.telemetry.materializer import materialize_pd_execution

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)


@router.post("/events")
async def ingest_event(payload: dict = Body(...)):
    event: TelemetryEvent | None = None
    try:
        event = validate_event_payload(payload)

        logger.info(
            "INGEST_RECEIVED",
            extra={
                "eventId": event.eventId,
                "requestId": event.correlation.requestId if event.correlation else None,
            },
        )

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
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
                json.dumps(payload),  # always store JSON text
            ),
        )

        conn.commit()
        conn.close()

        logger.info(
            "INGEST_PERSISTED",
            extra={
                "eventId": event.eventId,
                "requestId": event.correlation.requestId if event.correlation else None,
            },
        )

        # Materialize PD execution (best-effort, non-blocking)
        materialize_pd_execution(event)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Failed to ingest telemetry event",
            extra={
                "eventId": event.eventId if event else None,
                "requestId": event.correlation.requestId if event and event.correlation else None,
            },
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/events")
async def list_events():
    try:
        conn = get_connection()

        rows = conn.execute(
            """
            SELECT
                event_id,
                event_type,
                timestamp_utc,
                source_channel_id,
                source_environment,
                status,
                duration_ms,
                correlation_request_id,
                raw_payload
            FROM telemetry_events
            ORDER BY timestamp_utc DESC
            LIMIT 500
            """
        ).fetchall()

        conn.close()

        events = []

        for row in rows:
            raw_payload = row[8]
            parsed_raw = None

            if raw_payload:
                try:
                    parsed_raw = json.loads(raw_payload)
                except json.JSONDecodeError:
                    logger.warning(
                        "Invalid JSON raw_payload for telemetry event",
                        extra={"eventId": row[0]},
                    )
                    parsed_raw = raw_payload  # fallback to raw string

            events.append(
                {
                    "eventId": row[0],
                    "eventType": row[1],
                    "timestamp": row[2],
                    "source": {
                        "channelId": row[3],
                        "environment": row[4],
                    },
                    "outcome": {
                        "status": row[5],
                        "durationMs": row[6],
                    },
                    "correlation": {
                        "requestId": row[7],
                    },
                    "raw": parsed_raw,
                }
            )

        return events

    except Exception:
        logger.exception("Failed to list telemetry events")
        raise HTTPException(status_code=500, detail="Internal server error")
