import json
import logging
from typing import List

from fastapi import APIRouter, HTTPException

from app.db.connection import get_connection
from app.pd.models import PDExecution, PDExecutionCount
from app.pd.store import count_executions, list_executions

router = APIRouter(prefix="/pd-executions", tags=["pd-executions"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[PDExecution])
async def get_pd_executions():
    try:
        return list_executions()
    except Exception:
        logger.exception("Failed to load PD executions")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/count", response_model=PDExecutionCount)
async def get_pd_execution_count():
    try:
        return PDExecutionCount(count=count_executions())
    except Exception:
        logger.exception("Failed to count PD executions")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{request_id}/telemetry")
async def get_execution_telemetry(request_id: str):
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
            WHERE correlation_request_id = ?
            ORDER BY timestamp_utc ASC
            """,
            (request_id,),
        ).fetchall()

        conn.close()

        events = []
        for row in rows:
            raw_payload = row[8]
            parsed_raw = None
            if raw_payload:
                try:
                    parsed_raw = json.loads(raw_payload)
                except (json.JSONDecodeError, TypeError):
                    parsed_raw = raw_payload
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
        logger.exception("Failed to load PD execution telemetry")
        raise HTTPException(status_code=500, detail="Internal server error")
