from app.findings.models import FindingCreate, FindingOut, FindingsCountOut
from app.findings.repository import (
    add_or_update_finding,
    get_finding_by_id,
    get_findings_counts,
    list_findings,
    update_finding_status,
)


# ============================================================
# HELPERS
# ============================================================

def _resolve_org_name(source_oid: str | None, org_name: str | None) -> str | None:
    if not source_oid:
        return None
    return org_name or "Unrecognized Organization"


def _format_dt(value):
    """Convert datetime → ISO string for API"""
    if not value:
        return None
    return value.isoformat()


def _normalize_filter(value: str | None) -> str | None:
    if not value or value.lower() == "all":
        return None
    return value


def _normalize_execution_type(value: str | None) -> str | None:
    if not value or value.lower() == "all":
        return None
    return value.upper()


def _to_finding_out(row: dict) -> FindingOut:
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
        relatedOid=row.get("source_oid"),
        organization=_resolve_org_name(
            row.get("source_oid"),
            row.get("organization_name"),
        ),
        firstSeenAt=_format_dt(row.get("first_seen_at")),
        lastSeenAt=_format_dt(row.get("last_seen_at")),
        createdAt=_format_dt(row.get("created_at")),
        updatedAt=_format_dt(row.get("updated_at")),
    )


# ============================================================
# FETCH FINDINGS
# ============================================================

def fetch_findings(
    *,
    limit: int | None,
    offset: int,
    severity: str | None,
    status: str | None,
    category: str | None,
    execution_type: str | None,
    execution_id: str | None,
    q: str | None,
    sort: str,
    order: str,
) -> list[FindingOut]:

    rows = list_findings(
        limit=limit,
        offset=offset,
        severity=_normalize_filter(severity),
        status=_normalize_filter(status),
        category=_normalize_filter(category),
        execution_type=_normalize_execution_type(execution_type),
        execution_id=execution_id,
        q=q,
        sort=sort,
        order=order,
    )

    return [_to_finding_out(row) for row in rows]


# ============================================================
# COUNTS
# ============================================================

def fetch_findings_count(
    *,
    severity: str | None,
    status: str | None,
    execution_type: str | None,
) -> FindingsCountOut:

    counts = get_findings_counts(
        severity=_normalize_filter(severity),
        status=_normalize_filter(status),
        execution_type=_normalize_execution_type(execution_type),
    )

    return FindingsCountOut(**counts)


# ============================================================
# GET SINGLE
# ============================================================

def fetch_finding_by_id(finding_id: str) -> FindingOut | None:
    row = get_finding_by_id(finding_id)
    if not row:
        return None
    return _to_finding_out(row)


# ============================================================
# UPDATE STATUS
# ============================================================

def set_finding_status(*, finding_id: str, status: str) -> FindingOut | None:
    row = update_finding_status(finding_id=finding_id, status=status)
    if not row:
        return None
    return _to_finding_out(row)


# ============================================================
# DEMO SEED
# ============================================================

def seed_demo_findings(execution_id: str) -> int:
    demo_findings = [
        FindingCreate(
            id=f"finding-demo-{execution_id}-001",
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
            id=f"finding-demo-{execution_id}-002",
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
            id=f"finding-demo-{execution_id}-003",
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

    return len(demo_findings)


# ============================================================
# CREATE
# ============================================================

def create_finding(payload: FindingCreate) -> FindingOut:
    add_or_update_finding(
        id=payload.id,
        execution_id=payload.executionId,
        execution_type=payload.executionType,
        severity=payload.severity,
        category=payload.category,
        summary=payload.summary,
        technical_detail=payload.technicalDetail,
        recommended_action=payload.recommendedAction,
        status=payload.status,
    )

    row = get_finding_by_id(payload.id)
    return _to_finding_out(row)