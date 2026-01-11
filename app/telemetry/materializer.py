import logging
from datetime import datetime, timedelta

from app.pd.store import upsert_execution
from app.telemetry.models import TelemetryEvent

logger = logging.getLogger(__name__)

PD_EVENT_TYPE = "pd.request.complete"


def _parse_timestamp(value: str) -> datetime:
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def materialize_pd_execution(event: TelemetryEvent) -> None:
    try:
        logger.info(
            "MATERIALIZE_ENTERED",
            extra={
                "eventId": event.eventId,
                "requestId": event.correlation.requestId if event.correlation else None,
            },
        )

        if event.eventType != PD_EVENT_TYPE:
            logger.info(
                "MATERIALIZE_SKIPPED",
                extra={
                    "eventId": event.eventId,
                    "reason": "event_type_mismatch",
                },
            )
            return

        if not event.correlation or not event.correlation.requestId:
            logger.info(
                "MATERIALIZE_SKIPPED",
                extra={
                    "eventId": event.eventId,
                    "reason": "missing_request_id",
                },
            )
            return

        duration_ms = (
            event.outcome.durationMs
            if event.outcome and event.outcome.durationMs is not None
            else 0
        )

        completed_at = _parse_timestamp(event.timestamp)
        started_at = completed_at - timedelta(milliseconds=duration_ms)

        outcome_status = (
            event.outcome.status.lower()
            if event.outcome and event.outcome.status
            else ""
        )
        outcome = "success" if outcome_status == "success" else "failure"

        upsert_execution(
            request_id=event.correlation.requestId,
            event_id=event.eventId,
            started_at=started_at.isoformat().replace("+00:00", "Z"),
            completed_at=completed_at.isoformat().replace("+00:00", "Z"),
            duration_ms=duration_ms,
            outcome=outcome,
            source_channel_id=event.source.channelId if event.source else None,
            source_environment=event.source.environment if event.source else None,
        )

    except Exception:
        logger.exception(
            "Failed to materialize PD execution",
            extra={
                "eventId": event.eventId,
                "requestId": event.correlation.requestId if event.correlation else None,
            },
        )
        raise
