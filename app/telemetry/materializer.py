import logging
from datetime import timedelta

from app.pd.store import upsert_execution
from app.telemetry.models import TelemetryEvent

logger = logging.getLogger(__name__)

PD_EVENT_TYPE = "pd.request.completed"


def materialize_pd_execution(event: TelemetryEvent) -> None:
    if event.eventType != PD_EVENT_TYPE:
        return

    if not event.correlation or not event.correlation.requestId:
        logger.warning("PD event missing requestId", extra={"eventId": event.eventId})
        return

    duration_ms = 0
    if event.execution and event.execution.durationMs is not None:
        duration_ms = event.execution.durationMs

    completed_at = event.timestamp
    started_at = completed_at - timedelta(milliseconds=duration_ms)

    outcome_status = None
    if event.outcome and event.outcome.status:
        outcome_status = event.outcome.status

    success = outcome_status == "SUCCESS"
    outcome = "success" if success else "failure"

    try:
        upsert_execution(
            request_id=event.correlation.requestId,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_ms=duration_ms,
            outcome=outcome,
            success=success,
        )
    except Exception:
        logger.exception("Failed to materialize PD execution", extra={"eventId": event.eventId})
