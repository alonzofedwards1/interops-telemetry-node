import json
import logging
import requests
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from app.auth.dependencies import require_auth
from app.db.connection import get_connection
from app.telemetry.models import TelemetryEvent
from app.telemetry.validator import validate_event_payload
from app.pd.materialization_trigger import materialize_pd_execution

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)

@router.post("/events")
async def ingest_event(payload: dict = Body(...), user_id: int = Depends(require_auth)):
    try:
        event = validate_event_payload(payload)

        generated_event_id = event.eventId
        created_at = datetime.now(timezone.utc).isoformat()
        event_layer = payload.get("eventLayer") or payload.get("event_layer")

        cert_status = None
        cert_thumbprint = None

        if event_layer == "TRANSPORT":
            cert_status = payload.get("certStatus") or payload.get("cert_status")
            cert_thumbprint = payload.get("certThumbprint") or payload.get("cert_thumbprint")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO telemetry_events (
                event_id,
                event_type,
                event_layer,
                timestamp_utc,
                source_channel_id,
                source_environment,
                status,
                duration_ms,
                correlation_request_id,
                cert_status,
                cert_thumbprint,
                raw_payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                generated_event_id,
                event.eventType,
                event_layer,
                created_at,
                payload.get("sourceChannelId"),
                payload.get("sourceEnvironment"),
                payload.get("status"),
                payload.get("durationMs"),
                event.correlation.requestId if event.correlation else None,
                cert_status,
                cert_thumbprint,
                json.dumps(payload),
            ),
        )

        conn.commit()
        conn.close()

        materialize_pd_execution(event)

        return {"status": "ok"}

    except Exception:
        logger.exception("Failed to ingest telemetry event")
        raise HTTPException(status_code=500, detail="Internal server error")


# -------------------------------------------------------
# OPENHIM MACHINE-TO-MACHINE INGEST
# -------------------------------------------------------
@router.post("/ingest-openhim")
async def ingest_openhim_event(request: Request, payload: dict = Body(...)) -> dict[str, str]:
    generated_event_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # IMPORTANT:
    # This header must be injected in OpenHIM route:
    # Header: X-OpenHIM-Tx-Id
    # Value: {{transactionId}}
    transaction_id = request.headers.get("X-OpenHIM-Tx-Id")

    status = None
    duration_ms = None
    source_channel_id = None
    cert_status = None
    cert_thumbprint = None

    if transaction_id:
        try:
            openhim_url = f"http://openhim-core:8080/transactions/{transaction_id}"

            response = requests.get(
                openhim_url,
                auth=("root@openhim.org", "openhim-password"),
                timeout=3,
            )
            response.raise_for_status()

            transaction = response.json()

            source_channel_id = transaction.get("channel", {}).get("id")
            status = transaction.get("response", {}).get("status")
            duration_ms = transaction.get("response", {}).get("responseTime")

            cert_status = (
                transaction.get("tls", {})
                .get("clientCert", {})
                .get("subject")
            )

            cert_thumbprint = (
                transaction.get("tls", {})
                .get("clientCert", {})
                .get("fingerprint")
            )

            logger.info(
                "OPENHIM_METADATA_FETCH_SUCCESS",
                extra={
                    "eventId": generated_event_id,
                    "transactionId": transaction_id,
                    "channelId": source_channel_id,
                },
            )

        except Exception:
            logger.exception(
                "OPENHIM_METADATA_FETCH_FAILURE",
                extra={
                    "eventId": generated_event_id,
                    "transactionId": transaction_id,
                },
            )
    else:
        logger.info(
            "OPENHIM_TRANSACTION_ID_MISSING",
            extra={"eventId": generated_event_id},
        )

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO telemetry_events (
                event_id,
                event_type,
                event_layer,
                timestamp_utc,
                source_channel_id,
                source_environment,
                status,
                duration_ms,
                correlation_request_id,
                cert_status,
                cert_thumbprint,
                raw_payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                generated_event_id,
                "OPENHIM",
                "INGEST",
                created_at,
                source_channel_id,
                "openhim",
                status,
                duration_ms,
                transaction_id,
                cert_status,
                cert_thumbprint,
                json.dumps(payload),
            ),
        )

        conn.commit()
        conn.close()

        logger.info(
            "INGEST_PERSISTED_OPENHIM",
            extra={
                "eventId": generated_event_id,
                "transactionId": transaction_id,
            },
        )

        return {
            "status": "accepted",
            "source": "openhim",
            "eventId": generated_event_id,
        }

    except Exception:
        logger.exception(
            "Failed to persist OpenHIM telemetry event",
            extra={
                "eventId": generated_event_id,
                "transactionId": transaction_id,
            },
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# -------------------------------------------------------
# LIST EVENTS
# -------------------------------------------------------
@router.get("/events")
async def list_events(user_id: int = Depends(require_auth)):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
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
        )

        rows = cursor.fetchall()
        conn.close()

        events = []

        for row in rows:
            raw_payload = row[8]

            try:
                parsed_raw = json.loads(raw_payload) if raw_payload else None
            except Exception:
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
        logger.exception("Failed to list telemetry events")
        raise HTTPException(status_code=500, detail="Internal server error")