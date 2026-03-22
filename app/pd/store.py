import logging
from typing import List

from app.db.connection import get_connection
from app.pd.models import PDExecution

logger = logging.getLogger(__name__)


# =========================================================
# HELPERS
# =========================================================

def _format_dt(value):
    if not value:
        return None
    return value.isoformat()


# =========================================================
# UPSERT PD EXECUTION (FIXED)
# =========================================================

def upsert_execution(
    *,
    request_id: str,
    event_id: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    duration_ms: int | None = None,
    outcome: str | None = None,
    transaction_type: str = "PD",
    source_channel_id: str | None = None,
    source_environment: str | None = None,
    source_oid: str | None = None,
    target_oid: str | None = None,
    cert_status: str | None = None,
    cert_thumbprint: str | None = None,
    failure_stage: str | None = None,
    root_cause: str | None = None,
    http_status: int | None = None,
    retry_count: int | None = None,
) -> None:

    try:
        conn = get_connection()

        conn.execute(
            """
            INSERT INTO pd_executions (
                request_id,
                started_at,
                completed_at,
                duration_ms,
                outcome,
                transaction_type,
                source_channel_id,
                source_environment,
                cert_status,
                cert_thumbprint,
                failure_stage,
                root_cause,
                http_status,
                source_oid,
                target_oid,
                retry_count,
                first_event_id,
                last_event_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                started_at = COALESCE(excluded.started_at, pd_executions.started_at),
                completed_at = COALESCE(excluded.completed_at, pd_executions.completed_at),
                duration_ms = COALESCE(excluded.duration_ms, pd_executions.duration_ms),
                outcome = COALESCE(excluded.outcome, pd_executions.outcome),
                transaction_type = COALESCE(excluded.transaction_type, pd_executions.transaction_type),
                source_channel_id = COALESCE(excluded.source_channel_id, pd_executions.source_channel_id),
                source_environment = COALESCE(excluded.source_environment, pd_executions.source_environment),
                cert_status = COALESCE(excluded.cert_status, pd_executions.cert_status),
                cert_thumbprint = COALESCE(excluded.cert_thumbprint, pd_executions.cert_thumbprint),
                failure_stage = COALESCE(excluded.failure_stage, pd_executions.failure_stage),
                root_cause = COALESCE(excluded.root_cause, pd_executions.root_cause),
                http_status = COALESCE(excluded.http_status, pd_executions.http_status),
                source_oid = COALESCE(excluded.source_oid, pd_executions.source_oid),
                target_oid = COALESCE(excluded.target_oid, pd_executions.target_oid),
                retry_count = COALESCE(excluded.retry_count, pd_executions.retry_count),
                last_event_id = excluded.last_event_id
            """,
            (
                request_id,
                started_at,
                completed_at,
                duration_ms,
                outcome,
                transaction_type,
                source_channel_id,
                source_environment,
                cert_status,
                cert_thumbprint,
                failure_stage,
                root_cause,
                http_status,
                source_oid,
                target_oid,
                retry_count,
                event_id,  # first_event_id
                event_id,  # last_event_id
            ),
        )

        conn.commit()
        conn.close()

    except Exception:
        logger.exception("FAILED_TO_UPSERT_PD_EXECUTION", extra={"requestId": request_id})
        raise


# =========================================================
# READ EXECUTIONS (FIXED)
# =========================================================

def list_executions(limit: int = 500) -> List[PDExecution]:
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            request_id,
            started_at,
            completed_at,
            duration_ms,
            outcome,
            source_channel_id,
            source_environment,
            source_oid,
            od.organization_name AS source_org_name,
            cert_status,
            cert_thumbprint,
            failure_stage,
            root_cause,
            http_status
        FROM pd_executions
        LEFT JOIN oid_directory od
            ON LOWER(TRIM(pd_executions.source_oid)) = LOWER(TRIM(od.oid))
        ORDER BY completed_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    conn.close()

    return [
        PDExecution(
            requestId=row["request_id"],
            startedAt=_format_dt(row["started_at"]),
            completedAt=_format_dt(row["completed_at"]),
            executionTimeMs=row["duration_ms"],
            outcome=row["outcome"],
            channelId=row["source_channel_id"],
            environment=row["source_environment"],
            sourceOid=row["source_oid"],
            sourceOrganizationName=(
                "—"
                if not row["source_oid"]
                else row["source_org_name"] or "Unrecognized Organization"
            ),
            certStatus=row["cert_status"] or "NOT_REPORTED",
            certThumbprint=row["cert_thumbprint"],
            failureStage=row["failure_stage"],
            rootCause=row["root_cause"],
            httpStatus=row["http_status"],
        )
        for row in rows
    ]


# =========================================================
# TELEMETRY LOOKUP
# =========================================================

def get_execution_telemetry_events(request_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                event_id,
                event_type,
                timestamp_utc,
                source_channel_id,
                source_environment,
                status,
                duration_ms,
                correlation_request_id,
                raw_payload
            FROM telemetry_events
            WHERE correlation_request_id = ?
            ORDER BY timestamp_utc ASC
            """,
            (request_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


# =========================================================
# COUNT
# =========================================================

def count_executions() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) FROM pd_executions").fetchone()
    conn.close()
    return int(row[0]) if row else 0