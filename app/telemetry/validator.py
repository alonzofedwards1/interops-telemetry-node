import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import HTTPException
from pydantic import ValidationError

from .models import CorrelationInfo, OutcomeInfo, SourceInfo, TelemetryEvent

logger = logging.getLogger(__name__)


def _parse_timestamp(value: str) -> str:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_field(payload: Dict, field: str) -> str:
    value = payload.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", field], "msg": "field required", "type": "value_error.missing"}],
        )
    return value


def _normalize_source(source: Optional[Dict]) -> Optional[SourceInfo]:
    if not isinstance(source, dict):
        return None
    return SourceInfo(
        channelId=source.get("channelId"),
        environment=source.get("environment"),
    )


def _normalize_correlation(correlation: Optional[Dict]) -> Optional[CorrelationInfo]:
    if not isinstance(correlation, dict):
        return None
    return CorrelationInfo(requestId=correlation.get("requestId"))


def _normalize_outcome(outcome: Optional[Dict]) -> Optional[OutcomeInfo]:
    if not isinstance(outcome, dict):
        return None
    return OutcomeInfo(
        status=outcome.get("status"),
        durationMs=outcome.get("durationMs"),
    )


def _extract_oid(payload: Dict, key: str) -> Optional[str]:
    return payload.get(key) or payload.get(key.replace("_oid", "Oid"))


def validate_event_payload(payload: Dict) -> TelemetryEvent:
    """Normalize raw telemetry payload into a TelemetryEvent model."""

    try:
        event_id = _require_field(payload, "eventId")
        event_type = _require_field(payload, "eventType")
        timestamp = _require_field(payload, "timestamp")

        normalized_payload = {
            "eventId": event_id,
            "eventType": event_type,
            "timestamp": _parse_timestamp(timestamp),
            "source": _normalize_source(payload.get("source")),
            "correlation": _normalize_correlation(payload.get("correlation")),
            "outcome": _normalize_outcome(payload.get("outcome")),
            "sourceOid": _extract_oid(payload, "source_oid"),
            "targetOid": _extract_oid(payload, "target_oid"),
        }
        return TelemetryEvent(**normalized_payload)
    except HTTPException:
        raise
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "Telemetry payload validation failed",
            extra={"errors": str(exc)},
        )
        raise HTTPException(status_code=422, detail="Invalid telemetry payload")
    except Exception:
        logger.exception("Unexpected error during telemetry validation")
        raise HTTPException(status_code=500, detail="Internal server error")
