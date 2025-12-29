import logging
from fastapi import APIRouter, Body, HTTPException, Response
from fastapi.responses import JSONResponse

from app.telemetry.models import TelemetryEvent
from app.telemetry.store import get_store
from app.telemetry.validator import validate_event_payload

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)
store = get_store()


@router.post("/events")
async def ingest_event(payload: dict = Body(...)) -> Response:
    try:
        event: TelemetryEvent = validate_event_payload(payload)
        logger.info(
            "Telemetry event received",
            extra={
                "eventId": event.eventId,
                "source": event.source.model_dump() if event.source else None,
                "status": event.outcome.status if event.outcome else None,
                "protocol": event.protocol.model_dump() if event.protocol else None,
            },
        )
        store.add(event)
        return JSONResponse(status_code=200, content={"status": "ok"})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error while ingesting telemetry event")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/events")
async def list_events():
    return store.get_all()
