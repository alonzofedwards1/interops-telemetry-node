from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.transport.ingest_openhim import (
    OpenHIMUnavailableError,
    ingest_openhim_transactions,
    is_openhim_transaction,
    is_fhir_bundle,
    openhim_healthcheck,
    process_openhim_transaction,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class TransportIngestResponse(BaseModel):
    status: str
    source: str
    mode: str
    transaction_id: str | None = None
    processed: int = 0
    skipped: int = 0


class OpenHIMHealthResponse(BaseModel):
    status: str
    source: str


def _is_pull_request(payload: dict[str, Any]) -> bool:
    mode = payload.get("mode")
    return mode == "pull" or payload.get("pull") is True


@router.post(
    "/api/transport/ingest-openhim",
    response_model=TransportIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_openhim(request: Request) -> TransportIngestResponse:

    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        raise HTTPException(status_code=400, detail="Content-Type must be application/json")

    raw_body = await request.body()
    if not raw_body or not raw_body.strip():
        raise HTTPException(status_code=400, detail="Request body cannot be empty")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be JSON object")

    # Pull mode
    if _is_pull_request(payload):
        try:
            result = ingest_openhim_transactions()
        except OpenHIMUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

        return TransportIngestResponse(
            status="accepted",
            source="openhim",
            mode="pull",
            processed=result["processed"],
            skipped=result["skipped"],
        )

    # Push mode
    if is_openhim_transaction(payload):
        tx_id, was_skipped = process_openhim_transaction(payload)

        return TransportIngestResponse(
            status="accepted",
            source="openhim",
            mode="push",
            transaction_id=tx_id,
            processed=0 if was_skipped else 1,
            skipped=1 if was_skipped else 0,
        )

    # Reject FHIR bundle
    if is_fhir_bundle(payload):
        raise HTTPException(
            status_code=400,
            detail="FHIR Bundle payloads not accepted by transport ingest",
        )

    raise HTTPException(
        status_code=400,
        detail="Payload must be OpenHIM transaction or pull request",
    )


@router.get(
    "/api/transport/openhim-health",
    response_model=OpenHIMHealthResponse,
)
async def transport_openhim_health() -> OpenHIMHealthResponse:
    if not openhim_healthcheck():
        return JSONResponse(
            status_code=503,
            content=OpenHIMHealthResponse(status="degraded", source="openhim").model_dump(),
        )
    return OpenHIMHealthResponse(status="ok", source="openhim")