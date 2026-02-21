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
    is_fhir_bundle,
    is_openhim_transaction,
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


def _get_correlation_id(request: Request) -> str | None:
    return request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")


def _is_pull_request(payload: dict[str, Any]) -> bool:
    mode = payload.get("mode")
    return mode == "pull" or payload.get("pull") is True


@router.post(
    "/api/transport/ingest-openhim",
    response_model=TransportIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_openhim(request: Request) -> TransportIngestResponse:
    """Transport-layer ingest endpoint for OpenHIM push/pull modes."""

    correlation_id = _get_correlation_id(request)
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
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    tx_header = request.headers.get("X-OpenHIM-TransactionID")

    if _is_pull_request(payload):
        limit = payload.get("limit")
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise HTTPException(status_code=400, detail="limit must be a positive integer")

        try:
            result = ingest_openhim_transactions(limit=limit, correlation_id=correlation_id)
        except OpenHIMUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

        return TransportIngestResponse(
            status="accepted",
            source="openhim",
            mode="pull",
            processed=result["processed"],
            skipped=result["skipped"],
        )

    if is_openhim_transaction(payload):
        tx_id, was_skipped = process_openhim_transaction(
            payload,
            correlation_id=correlation_id,
        )

        # Loop protection: if header transaction id is present and already stored, skip deterministically.
        if tx_header and tx_header == tx_id and was_skipped:
            logger.info(
                "transport_ingest_loop_prevented",
                extra={
                    "transaction_id": tx_id,
                    "channel": payload.get("channelID"),
                    "reason": "existing_transaction_header",
                    "correlation_id": correlation_id,
                },
            )

        return TransportIngestResponse(
            status="accepted",
            source="openhim",
            mode="push",
            transaction_id=tx_id,
            processed=0 if was_skipped else 1,
            skipped=1 if was_skipped else 0,
        )

    if is_fhir_bundle(payload):
        logger.warning(
            "transport_ingest_bundle_rejected",
            extra={"correlation_id": correlation_id, "reason": "bundle_not_supported_for_transport_store"},
        )
        raise HTTPException(
            status_code=400,
            detail="FHIR Bundle payloads are not accepted by transport ingest; send OpenHIM transaction or pull mode request",
        )

    logger.warning(
        "transport_ingest_invalid_payload",
        extra={
            "transaction_id": tx_header,
            "channel": payload.get("channelID"),
            "reason": "not_openhim_transaction_or_bundle",
            "correlation_id": correlation_id,
        },
    )
    raise HTTPException(
        status_code=400,
        detail="Payload must be a valid OpenHIM transaction object or pull mode request",
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
