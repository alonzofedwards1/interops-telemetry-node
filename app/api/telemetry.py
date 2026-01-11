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
    try:
        # ✅ Validate payload → TelemetryEvent
        event: TelemetryEvent = validate_event_payload(payload)

        # ✅ Persist raw telemetry event
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
                payload,
            ),
        )

        conn.commit()
        conn.close()

        # 🔥 INLINE materialization (NO BackgroundTasks)
        materialize_pd_execution(event)

        logger.info(
            "Telemetry event ingested and materialized",
            extra={"eventId": event.eventId},
        )

        return {"status": "ok"}

    except Exception:
        logger.exception("Failed to ingest telemetry event")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/events")
async def list_events():
    try:
        conn = get_connection()
        conn.row_factory = None

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

        return [
            {
                "eventId": r[0],
                "eventType": r[1],
                "timestamp": r[2],
                "source": {
                    "channelId": r[3],
                    "environment": r[4],
                },
                "outcome": {
                    "status": r[5],
                    "durationMs": r[6],
                },
                "correlation": {
                    "requestId": r[7],
                },
                "raw": r[8],
            }
            for r in rows
        ]

    except Exception:
        logger.exception("Failed to list telemetry events")
        raise HTTPException(status_code=500, detail="Internal server error")
