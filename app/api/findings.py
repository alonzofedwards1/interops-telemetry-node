import logging
from typing import List

from fastapi import APIRouter, Body, HTTPException, Query

from app.config.settings import get_settings
from app.findings.models import FindingCreate, FindingOut, FindingStatusUpdate, FindingsCountOut
from app.findings.repository import (
    add_or_update_finding,
    get_finding_by_id,
    get_findings_counts,
    list_findings,
    update_finding_status,
)

router = APIRouter(prefix="/findings", tags=["findings"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.get("", response_model=List[FindingOut])
async def get_findings(
    limit: int = Query(50, ge=1, le=200),
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
    try:
        logger.info(
            "FINDINGS_LIST",
            extra={
                "limit": limit,
                "offset": offset,
                "severity": severity,
                "status": status,
                "category": category,
                "execution_type": execution_type,
                "execution_id": execution_id,
                "q": q,
            },
        )
        rows = list_findings(
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
        return [
            FindingOut(
                id=row["id"],
                executionId=row.get("execution_id"),
                executionType=row.get("execution_type"),
                severity=row["severity"],
                category=row["category"],
                summary=row["summary"],
                technicalDetail=row.get("technical_detail"),
                recommendedAction=row.get("recommended_action"),
                status=row["status"],
                firstSeenAt=row.get("first_seen_at"),
                lastSeenAt=row.get("last_seen_at"),
                createdAt=row.get("created_at"),
                updatedAt=row.get("updated_at"),
            )
            for row in rows
        ]
    except Exception:
        logger.exception("Failed to list findings")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/count", response_model=FindingsCountOut)
async def get_findings_count(
    severity: str | None = None,
    status: str | None = None,
    execution_type: str | None = None,
):
    try:
        logger.info(
            "FINDINGS_COUNT",
            extra={
                "severity": severity,
                "status": status,
                "execution_type": execution_type,
            },
        )
        counts = get_findings_counts(
            severity=severity,
            status=status,
            execution_type=execution_type,
        )
        return FindingsCountOut(**counts)
    except Exception:
        logger.exception("Failed to get findings count")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{finding_id}", response_model=FindingOut)
async def get_finding(finding_id: str):
    try:
        logger.info("FINDING_DETAIL", extra={"finding_id": finding_id})
        row = get_finding_by_id(finding_id)
        if not row:
            raise HTTPException(status_code=404, detail="Finding not found")
        return FindingOut(
            id=row["id"],
            executionId=row.get("execution_id"),
            executionType=row.get("execution_type"),
            severity=row["severity"],
            category=row["category"],
            summary=row["summary"],
            technicalDetail=row.get("technical_detail"),
            recommendedAction=row.get("recommended_action"),
            status=row["status"],
            firstSeenAt=row.get("first_seen_at"),
            lastSeenAt=row.get("last_seen_at"),
            createdAt=row.get("created_at"),
            updatedAt=row.get("updated_at"),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get finding")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/seed-demo")
async def seed_demo_findings(payload: dict = Body(None)):
    try:
        if settings.environment.lower() == "prod":
            raise HTTPException(status_code=403, detail="Not allowed in production")

        execution_id = None
        if isinstance(payload, dict):
            execution_id = payload.get("execution_id") or payload.get("executionId")
        execution_id = execution_id or "req-local-001"

        logger.info(
            "FINDINGS_SEED",
            extra={"execution_id": execution_id},
        )

        demo_findings = [
            FindingCreate(
                id="finding-demo-001",
                executionId=execution_id,
                executionType="PD",
                severity="critical",
                category="Patient Match",
                summary="No patient match found",
                technicalDetail="MPI lookup returned 0 matches",
                recommendedAction="Verify patient demographics and retry",
                status="open",
            ),
            FindingCreate(
                id="finding-demo-002",
                executionId=execution_id,
                executionType="PD",
                severity="warning",
                category="Latency",
                summary="Execution exceeded expected latency",
                technicalDetail="Observed duration > 2s threshold",
                recommendedAction="Inspect downstream system response times",
                status="acknowledged",
            ),
            FindingCreate(
                id="finding-demo-003",
                executionId=execution_id,
                executionType="PD",
                severity="info",
                category="Audit",
                summary="Request completed successfully",
                technicalDetail=None,
                recommendedAction=None,
                status="resolved",
            ),
        ]

        for finding in demo_findings:
            add_or_update_finding(
                id=finding.id,
                execution_id=finding.executionId,
                execution_type=finding.executionType,
                severity=finding.severity,
                category=finding.category,
                summary=finding.summary,
                technical_detail=finding.technicalDetail,
                recommended_action=finding.recommendedAction,
                status=finding.status,
            )

        return {"status": "ok", "count": len(demo_findings)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to seed demo findings")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{finding_id}/status", response_model=FindingOut)
async def update_status(finding_id: str, payload: FindingStatusUpdate):
    try:
        logger.info(
            "FINDING_STATUS_UPDATE",
            extra={"finding_id": finding_id, "status": payload.status},
        )
        row = update_finding_status(finding_id=finding_id, status=payload.status)
        if not row:
            raise HTTPException(status_code=404, detail="Finding not found")
        return FindingOut(
            id=row["id"],
            executionId=row.get("execution_id"),
            executionType=row.get("execution_type"),
            severity=row["severity"],
            category=row["category"],
            summary=row["summary"],
            technicalDetail=row.get("technical_detail"),
            recommendedAction=row.get("recommended_action"),
            status=row["status"],
            firstSeenAt=row.get("first_seen_at"),
            lastSeenAt=row.get("last_seen_at"),
            createdAt=row.get("created_at"),
            updatedAt=row.get("updated_at"),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update finding status")
        raise HTTPException(status_code=500, detail="Internal server error")
