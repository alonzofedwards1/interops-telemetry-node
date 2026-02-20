import json
import logging
import requests
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from app.auth.dependencies import require_auth
from app.db.connection import get_connection
from app.oids.repository import register_observed_oid
from app.telemetry.models import TelemetryEvent
from app.telemetry.validator import validate_event_payload
from app.pd.materialization_trigger import materialize_pd_execution


router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)


def _extract_oid(payload: dict, key: str) -> str | None:
    return payload.get(key) or payload.get(key.replace("_oid", "Oid"))


def _register_oid_safe(oid: str | None) -> None:
    if not oid:
        return
    try:
        register_observed_oid(oid, None)
    except Exception:
        logger.exception("Failed to register observed OID", extra={"oid": oid})


@router.post("/events")
async def ingest_event(payload: dict = Body(...), user_id: int = Depends(require_auth)):
    event: TelemetryEvent | None = None
    try:
        event = validate_event_payload(payload)
        event_layer = payload.get("eventLayer") or payload.get("event_layer")
        cert_status = None
        cert_thumbprint = None
        if event_layer == "TRANSPORT":
            cert_status = payload.get("certStatus") or payload.get("cert_status")
            cert_thumbprint = payload.get("certThumbprint") or payload.get("cert_thumbprint")

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("eventId"),
                payload.get("eventType"),
                event_layer,
                payload.get("timestamp"),
                event.source.channelId if event.source else None,
                event.source.environment if event.source else None,
                event.outcome.status if event.outcome else None,
                event.outcome.durationMs if event.outcome else None,
                event.correlation.requestId if event.correlation else None,
                cert_status,
                cert_thumbprint,
                json.dumps(payload),
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


@router.post("/ingest-openhim")
async def ingest_openhim_event(request: Request, payload: dict = Body(...)) -> dict[str, str]:
    """This endpoint is used for machine-to-machine ingestion from OpenHIM and bypasses user authentication."""
    generated_event_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    transaction_id = (
        request.headers.get("X-OpenHIM-TransactionID")
        or request.headers.get("X-OpenHIM-TransactionId")
        or payload.get("transactionID")
        or payload.get("transactionId")
    )

    status = None
    duration_ms = None
    source_channel_id = None
    cert_status = None
    cert_thumbprint = None

    if transaction_id and not request.headers.get("X-OpenHIM-TransactionID") and not request.headers.get("X-OpenHIM-TransactionId"):
        logger.info(
            "Using transaction identifier from payload",
            extra={"source": "openhim", "eventId": generated_event_id, "transactionId": transaction_id},
        )

    if transaction_id:
        try:
            openhim_url = f"http://openhim-core:8080/transactions/{transaction_id}"
            resp = requests.get(openhim_url, timeout=3)
            resp.raise_for_status()
            transaction = resp.json()

            status = transaction.get("response", {}).get("status")
            duration_ms = transaction.get("response", {}).get("time")
            source_channel_id = transaction.get("channelID")

            orchestrations = transaction.get("orchestrations", [])
            if orchestrations:
                tls = orchestrations[0].get("tls", {})
                cert_thumbprint = tls.get("fingerprint")
                cert_status = tls.get("authorized")
        except Exception:
            logger.exception(
                "Failed to fetch OpenHIM transaction metadata",
                extra={"source": "openhim", "eventId": generated_event_id, "transactionId": transaction_id},
            )
    else:
        logger.info(
            "OpenHIM transaction identifier missing from header and payload",
            extra={"source": "openhim", "eventId": generated_event_id},
        )

    try:
        logger.info(
            "INGEST_RECEIVED_OPENHIM",
            extra={"source": "openhim", "eventId": generated_event_id, "transactionId": transaction_id},
        )

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
                "source": "openhim",
                "eventId": generated_event_id,
                "createdAt": created_at,
                "transactionId": transaction_id,
            },
        )

        return {"status": "accepted", "source": "openhim", "eventId": generated_event_id}

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Failed to ingest OpenHIM telemetry event",
            extra={"source": "openhim", "eventId": generated_event_id, "transactionId": transaction_id},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/events")
async def list_events(user_id: int = Depends(require_auth)):
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
        logger.exception("Failed to list telemetry events")
        raise HTTPException(status_code=500, detail="Internal server error")
