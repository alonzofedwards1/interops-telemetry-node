"""Converters that map OpenHIM transactions to normalized transport events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import TransportEvent, TransportRequest, TransportResponse


def _as_datetime(value: Any) -> datetime:
    """Convert known timestamp formats into timezone-aware UTC datetime."""

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, str) and value:
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return datetime.now(timezone.utc)


def _as_int(value: Any, default: int = 0) -> int:
    """Best-effort integer parsing for OpenHIM payload values."""

    if isinstance(value, bool):
        return default

    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_headers(value: Any) -> dict[str, Any]:
    """Return a dictionary for request headers; fallback to empty dict."""

    return value if isinstance(value, dict) else {}


def materialize_transaction(raw: dict[str, Any]) -> TransportEvent:
    """Normalize one raw OpenHIM transaction object into ``TransportEvent``."""

    request_data = raw.get("request", {}) or {}
    response_data = raw.get("response", {}) or {}

    transaction_id = (
        str(raw.get("_id") or raw.get("id") or raw.get("transactionID") or "")
        .strip()
        or "unknown"
    )

    return TransportEvent(
        transaction_id=transaction_id,
        channel=str(raw.get("channelID") or raw.get("channel") or "unknown"),
        request=TransportRequest(
            method=str(request_data.get("method") or "UNKNOWN"),
            url=str(request_data.get("path") or request_data.get("url") or ""),
            headers=_as_headers(request_data.get("headers") or {}),
        ),
        response=TransportResponse(
            status=_as_int(response_data.get("status") or response_data.get("statusCode")),
            duration_ms=_as_int(
                response_data.get("duration")
                or response_data.get("duration_ms")
                or raw.get("responseTime")
            ),
        ),
        source_ip=(request_data.get("clientIP") or raw.get("clientIP") or None),
        timestamp=_as_datetime(
            raw.get("created") or raw.get("timestamp") or raw.get("time")
        ),
    )
