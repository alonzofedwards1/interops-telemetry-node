"""Materializer for converting raw OpenHIM transactions to transport models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import TransportEvent, TransportRequest, TransportResponse


def _coerce_timestamp(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw:
        normalized = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    return datetime.now(timezone.utc)


def _read_status(response: dict[str, Any]) -> int:
    return int(
        response.get("status")
        or response.get("statusCode")
        or response.get("status_code")
        or 0
    )


def _read_duration_ms(raw_txn: dict[str, Any], response: dict[str, Any]) -> int:
    duration = (
        response.get("duration")
        or response.get("durationMs")
        or response.get("duration_ms")
        or raw_txn.get("duration")
        or raw_txn.get("durationMs")
        or raw_txn.get("duration_ms")
        or 0
    )
    return max(int(duration), 0)


def materialize_transaction(raw_txn: dict[str, Any]) -> TransportEvent:
    """Convert a raw OpenHIM transaction payload into a TransportEvent."""
    request = raw_txn.get("request") or {}
    response = raw_txn.get("response") or {}

    transaction_id = str(
        raw_txn.get("_id") or raw_txn.get("id") or raw_txn.get("transactionID") or ""
    )
    channel = str(raw_txn.get("channel") or raw_txn.get("channelID") or "unknown")

    normalized_request = TransportRequest(
        method=str(request.get("method") or "UNKNOWN"),
        url=str(request.get("url") or request.get("path") or ""),
        headers=request.get("headers") if isinstance(request.get("headers"), dict) else {},
    )

    normalized_response = TransportResponse(
        status=_read_status(response),
        duration_ms=_read_duration_ms(raw_txn, response),
    )

    return TransportEvent(
        transaction_id=transaction_id,
        channel=channel,
        request=normalized_request,
        response=normalized_response,
        source_ip=raw_txn.get("clientIP") or raw_txn.get("sourceIp") or request.get("remoteAddress"),
        timestamp=_coerce_timestamp(
            raw_txn.get("timestamp") or raw_txn.get("created") or raw_txn.get("requestTimestamp")
        ),
    )
