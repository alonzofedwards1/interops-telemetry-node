import logging
from app.telemetry.models import TelemetryEvent
from app.pd.materializer import materialize_execution_from_telemetry

logger = logging.getLogger(__name__)


def materialize_pd_execution(event: TelemetryEvent) -> None:
    """
    Trigger hook for PD execution materialization.

    PD is a TRANSACTION TYPE.
    PD_REQUEST / PD_RESPONSE are EVENT TYPES.
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

        # Only PD-related telemetry
        if event.eventType not in ("PD_REQUEST", "PD_RESPONSE"):
            return

        # Must have correlation_request_id
        if not event.correlation or not event.correlation.requestId:
            return

        # Only APPLICATION events can finalize a PD execution
        if event.eventLayer != "APPLICATION":
            return

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
