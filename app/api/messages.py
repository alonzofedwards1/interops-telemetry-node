from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter

from app.db.connection import get_connection

router = APIRouter()


def _normalize_transport_status(response_status: int | None) -> str:
    if response_status is None:
        return "Warning"
    if 200 <= response_status <= 299:
        return "Success"
    if 400 <= response_status <= 599:
        return "Error"
    return "Warning"


def _certificate_status(cert_not_after: datetime | None) -> str:
    now = datetime.now(timezone.utc)
    if cert_not_after is None:
        return "Valid"

    if cert_not_after.tzinfo is None:
        cert_not_after = cert_not_after.replace(tzinfo=timezone.utc)

    if cert_not_after < now:
        return "Expired"
    if cert_not_after <= now + timedelta(days=30):
        return "Expiring Soon"
    return "Valid"


@router.get("/api/messages")
async def list_messages(
    limit: int = 100,
    source: str | None = None,
    status: str | None = None,
    environment: str | None = None,
):
    """
    Unified message monitor endpoint.
    Returns normalized transport + telemetry events.
    """

    normalized_source = source.lower() if source else None
    rows: list[dict[str, Any]] = []

    conn = get_connection()
    try:
        if normalized_source in (None, "transport"):
            with conn.cursor() as cursor:
                transport_query = """
                    SELECT
                        id,
                        transaction_id,
                        channel,
                        response_status,
                        timestamp,
                        NULL::TEXT AS environment,
                        cert_sha256 AS cert_thumbprint,
                        cert_not_after
                    FROM transport_events
                    WHERE 1 = 1
                """
                transport_params: list[Any] = []

                if environment:
                    transport_query += " AND 1 = 0"

                transport_query += " ORDER BY timestamp DESC LIMIT %s"
                transport_params.append(limit)
                cursor.execute(transport_query, tuple(transport_params))
                transport_rows = cursor.fetchall()

            for transport in transport_rows:
                normalized_status = _normalize_transport_status(transport["response_status"])
                certificate = None
                if transport["cert_thumbprint"]:
                    certificate = {
                        "thumbprint": transport["cert_thumbprint"],
                        "status": _certificate_status(transport["cert_not_after"]),
                    }

                rows.append(
                    {
                        "id": transport["id"],
                        "source": "transport",
                        "timestamp": transport["timestamp"],
                        "status": normalized_status,
                        "eventType": "Transport",
                        "requestId": None,
                        "transactionId": transport["transaction_id"],
                        "channelId": transport["channel"],
                        "interactionId": transport["transaction_id"],
                        "durationMs": None,
                        "environment": transport["environment"],
                        "certificate": certificate,
                    }
                )

        if normalized_source in (None, "telemetry"):
            with conn.cursor() as cursor:
                telemetry_query = """
                    SELECT
                        event_id AS id,
                        timestamp_utc AS timestamp,
                        status,
                        event_type,
                        correlation_request_id AS request_id,
                        duration_ms,
                        source_environment AS environment
                    FROM telemetry_events
                    WHERE 1 = 1
                """
                telemetry_params: list[Any] = []
                if environment:
                    telemetry_query += " AND source_environment = %s"
                    telemetry_params.append(environment)

                telemetry_query += " ORDER BY timestamp_utc DESC LIMIT %s"
                telemetry_params.append(limit)
                cursor.execute(telemetry_query, tuple(telemetry_params))
                telemetry_rows = cursor.fetchall()

            for telemetry in telemetry_rows:
                rows.append(
                    {
                        "id": telemetry["id"],
                        "source": "telemetry",
                        "timestamp": telemetry["timestamp"],
                        "status": telemetry["status"],
                        "eventType": telemetry["event_type"],
                        "requestId": telemetry["request_id"],
                        "transactionId": None,
                        "channelId": None,
                        "interactionId": telemetry["request_id"],
                        "durationMs": telemetry["duration_ms"],
                        "environment": telemetry["environment"],
                        "certificate": None,
                    }
                )
    finally:
        conn.close()

    if status:
        rows = [event for event in rows if (event.get("status") or "").lower() == status.lower()]

    rows.sort(key=lambda event: event.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows[:limit]
