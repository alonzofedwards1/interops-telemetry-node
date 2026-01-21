# app/pd/materialization_trigger.py

import logging
from app.telemetry.models import TelemetryEvent
from app.pd.materializer import materialize_execution_from_telemetry

logger = logging.getLogger(__name__)


def materialize_pd_execution(event: TelemetryEvent) -> None:
    """
    Trigger hook for PD execution materialization.

    Responsibilities:
    - Inspect a single telemetry event
    - Decide whether it is eligible to trigger execution materialization
    - Delegate execution building to the PD materializer

    MUST NOT:
    - Write to the database
    - Infer duration or outcome
    - Build executions
    - Emit findings
    """

    try:
        logger.info(
            "PD_MATERIALIZATION_TRIGGER",
            extra={
                "eventId": event.eventId,
                "requestId": event.correlation.requestId if event.correlation else None,
                "eventType": event.eventType,
                "eventLayer": getattr(event, "eventLayer", None),
                "eventSubtype": getattr(event, "eventSubtype", None),
            },
        )

        # Only PD telemetry
        if event.eventType != "PD":
            return

        # Must have correlation_request_id
        if not event.correlation or not event.correlation.requestId:
            return

        # Only trigger on terminal-ish APPLICATION events
        # Transport-only events are insufficient to finalize an execution
        if event.eventLayer != "APPLICATION":
            return

        # Delegate to grouped materializer
        materialize_execution_from_telemetry(
            request_id=event.correlation.requestId
        )

    except Exception:
        logger.exception(
            "PD_MATERIALIZATION_TRIGGER_FAILED",
            extra={
                "eventId": event.eventId,
                "requestId": event.correlation.requestId if event.correlation else None,
            },
        )
        raise
