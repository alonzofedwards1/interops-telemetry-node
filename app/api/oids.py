import logging
from typing import List

from fastapi import APIRouter, Header, HTTPException, Query

from app.oids.models import OidDetail, OidGovernanceRequest, OidListItem, OidUsage
from app.oids.repository import (
    get_oid,
    get_oid_usage_counts,
    list_oids,
    update_oid_governance,
)

router = APIRouter(prefix="/oids", tags=["oids"])
logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def _confidence_label(score: float | None) -> str:
    if score is None:
        return "LOW"
    if score >= 0.75:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def _format_dt(value):
    """Convert datetime → ISO string"""
    if not value:
        return None
    return value.isoformat()


# ============================================================
# LIST OIDS
# ============================================================

@router.get("", response_model=List[OidListItem])
async def get_oids(
    status: str | None = None,
    confidence: str | None = None,
    sort: str = Query("last_seen", alias="sort"),
    order: str = "desc",
):
    try:
        sort = sort.lower()

        sort_map = {
            "last_seen": "last_seen_at",
            "oid": "oid",
            "status": "status",
        }

        rows = list_oids(
            status=status,
            confidence=confidence if confidence and confidence.lower() != "all" else None,
            sort=sort_map.get(sort, "last_seen_at"),
            order=order,
        )

        return [
            OidListItem(
                oid=row["oid"],
                displayName=row.get("organization_name"),
                ownerOrg=row.get("organization_name"),
                status=row["status"],
                confidence=_confidence_label(row.get("confidence_score")),
                firstSeen=_format_dt(row.get("first_seen_at")),
                lastSeen=_format_dt(row.get("last_seen_at")),
            )
            for row in rows
        ]

    except Exception:
        logger.exception("Failed to list OIDs")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================
# GET OID DETAIL
# ============================================================

@router.get("/{oid}", response_model=OidDetail)
async def get_oid_detail(oid: str):
    try:
        row = get_oid(oid)
        if not row:
            raise HTTPException(status_code=404, detail="OID not found")

        usage = get_oid_usage_counts(oid)

        return OidDetail(
            oid=row["oid"],
            displayName=row.get("organization_name"),
            ownerOrg=row.get("organization_name"),
            status=row["status"],
            confidence=_confidence_label(row.get("confidence_score")),
            firstSeen=_format_dt(row.get("first_seen_at")),
            lastSeen=_format_dt(row.get("last_seen_at")),
            usage=OidUsage(**usage),
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get OID detail")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================
# GOVERN OID
# ============================================================

@router.post("/{oid}/governance", response_model=OidDetail)
async def govern_oid(
    oid: str,
    payload: OidGovernanceRequest,
    x_role: str | None = Header(None, alias="X-Role"),
    x_reviewer: str | None = Header(None, alias="X-Reviewer"),
):
    try:
        if not x_role or x_role.lower() not in {"admin", "committee"}:
            raise HTTPException(status_code=403, detail="Forbidden")

        logger.info(
            "OID_GOVERNANCE",
            extra={
                "oid": oid,
                "action": payload.action,
                "reviewer": x_reviewer,
            },
        )

        updated = update_oid_governance(
            oid=oid,
            action=payload.action,
            owner_org=payload.ownerOrg,
            reviewed_by=x_reviewer,
        )

        if not updated:
            raise HTTPException(status_code=404, detail="OID not found")

        usage = get_oid_usage_counts(oid)

        return OidDetail(
            oid=updated["oid"],
            displayName=updated.get("organization_name"),
            ownerOrg=updated.get("organization_name"),
            status=updated["status"],
            confidence=_confidence_label(updated.get("confidence_score")),
            firstSeen=_format_dt(updated.get("first_seen_at")),
            lastSeen=_format_dt(updated.get("last_seen_at")),
            usage=OidUsage(**usage),
        )

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Failed to govern OID")
        raise HTTPException(status_code=500, detail="Internal server error")