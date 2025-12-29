import logging
from typing import Dict

from fastapi import HTTPException
from pydantic import ValidationError

from .models import TelemetryEvent

logger = logging.getLogger(__name__)


def validate_event_payload(payload: Dict) -> TelemetryEvent:
    """Validate raw telemetry payload into a TelemetryEvent model.

    Raises HTTPException with status 400 for validation issues to align with
    API expectations.
    """

    try:
        event = TelemetryEvent(**payload)
        return event
    except ValidationError as exc:
        logger.warning(
            "Telemetry payload validation failed",
            extra={"errors": exc.errors()},
        )
        raise HTTPException(status_code=400, detail=exc.errors())
    except Exception:
        logger.exception("Unexpected error during telemetry validation")
        raise HTTPException(status_code=500, detail="Internal server error")
