import logging
from typing import List

from fastapi import APIRouter, Body, HTTPException, Query

from app.config.settings import get_settings
from app.findings.models import FindingCreate, FindingOut, FindingStatusUpdate, FindingsCountOut
from app.findings.service import (
    create_finding,
    fetch_finding_by_id,
    fetch_findings,
    fetch_findings_count,
    seed_demo_findings,
    set_finding_status,
)

router = APIRouter(prefix="/findings", tags=["findings"])
logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# GET /findings
# ============================================================

@router.get("", response_model=List[FindingOut])
async def get_findings(
    # 🔥 FIX: limit is now OPTIONAL — no silent cap
    limit: int | None = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    severity: str | None = None,
    status: str | None = None,
    category: str | None = None,
    execution_type: str | None = None,
    execution_id: str | None = None,
    q: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
):
    """
    Returns findings.

    - If `limit` is omitted → ALL findings are returned
    - If `limit` is provided → paginated results
    """
    try:
        return fetch_findings(
            limit=limit,
            offset=offset,
            severity=severity,
            status=status,
            category=category,
            execution_type=execution_type,
            execution_id=execution_id,
            q=q,
            sort=sort,
            order=order,
        )

    except Exception:
        logger.exception("Failed to list findings")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================
# GET /findings/count  (AUTHORITATIVE METRICS SOURCE)
# ============================================================

@router.get("/count", response_model=FindingsCountOut)
async def get_findings_count(
    severity: str | None = None,
    status: str | None = None,
    execution_type: str | None = None,
):
    """
    Returns authoritative finding counts.
    This endpoint MUST be used by dashboard widgets.
    """
    try:
        return fetch_findings_count(
            severity=severity,
            status=status,
            execution_type=execution_type,
        )

    except Exception:
        logger.exception("Failed to get findings count")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================
# GET /findings/{id}
# ============================================================

@router.get("/{finding_id}", response_model=FindingOut)
async def get_finding(finding_id: str):
    try:
        finding = fetch_finding_by_id(finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        return finding

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get finding")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================
# PATCH /findings/{id}/status
# ============================================================

@router.patch("/{finding_id}/status", response_model=FindingOut)
async def update_status(finding_id: str, payload: FindingStatusUpdate):
    try:
        finding = set_finding_status(
            finding_id=finding_id,
            status=payload.status,
        )

        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        return finding

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update finding status")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================
# POST /findings/seed-demo
# ============================================================

@router.post("/seed-demo")
async def seed_demo_findings_endpoint(payload: dict = Body(None)):
    try:
        if settings.environment.lower() == "prod":
            raise HTTPException(status_code=403, detail="Not allowed in production")

        execution_id = None
        if isinstance(payload, dict):
            execution_id = payload.get("execution_id") or payload.get("executionId")
        execution_id = execution_id or "req-local-001"

        count = seed_demo_findings(execution_id)
        return {"status": "ok", "count": count}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to seed demo findings")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=FindingOut)
async def create_or_upsert_finding(payload: FindingCreate):
    try:
        create_finding(payload)
        return payload
    except Exception:
        logger.exception("Failed to create/upsert finding")
        raise HTTPException(status_code=500, detail="Internal server error")
