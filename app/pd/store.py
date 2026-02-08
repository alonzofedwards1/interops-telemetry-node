import logging
from typing import List

from app.db.connection import get_connection
from app.pd.models import PDExecution

logger = logging.getLogger(__name__)


# =========================================================
# UPSERT PD EXECUTION
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
) -> None:
    try:
        logger.info(
            "UPSERT_CALLED",
            extra={"requestId": request_id, "eventId": event_id},
        )

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

                cert_status,
                cert_thumbprint,
                failure_stage,
                root_cause,
                http_status,

                retry_count,
                first_event_id,
                last_event_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                started_at = COALESCE(excluded.started_at, pd_executions.started_at),
                completed_at = COALESCE(excluded.completed_at, pd_executions.completed_at),
                duration_ms = COALESCE(excluded.duration_ms, pd_executions.duration_ms),
                outcome = COALESCE(excluded.outcome, pd_executions.outcome),
                transaction_type = COALESCE(excluded.transaction_type, pd_executions.transaction_type),

                source_channel_id = COALESCE(excluded.source_channel_id, pd_executions.source_channel_id),
                source_environment = COALESCE(excluded.source_environment, pd_executions.source_environment),
                cert_status = CASE
                    WHEN pd_executions.cert_status IS NULL THEN excluded.cert_status
                    WHEN excluded.cert_status IS NULL THEN pd_executions.cert_status
                    WHEN (
                        CASE excluded.cert_status
                            WHEN 'UNTRUSTED' THEN 2
                            WHEN 'EXPIRED' THEN 2
                            WHEN 'INVALID' THEN 2
                            WHEN 'VALID' THEN 1
                            WHEN 'NOT_REPORTED' THEN 0
                            ELSE 0
                        END
                    ) > (
                        CASE pd_executions.cert_status
                            WHEN 'UNTRUSTED' THEN 2
                            WHEN 'EXPIRED' THEN 2
                            WHEN 'INVALID' THEN 2
                            WHEN 'VALID' THEN 1
                            WHEN 'NOT_REPORTED' THEN 0
                            ELSE 0
                        END
                    ) THEN excluded.cert_status
                    ELSE pd_executions.cert_status
                END,
                cert_thumbprint = COALESCE(excluded.cert_thumbprint, pd_executions.cert_thumbprint),
                failure_stage = COALESCE(excluded.failure_stage, pd_executions.failure_stage),
                root_cause = COALESCE(excluded.root_cause, pd_executions.root_cause),
                http_status = COALESCE(excluded.http_status, pd_executions.http_status),
                source_oid = COALESCE(excluded.source_oid, pd_executions.source_oid),
                target_oid = COALESCE(excluded.target_oid, pd_executions.target_oid),

                cert_status = COALESCE(excluded.cert_status, pd_executions.cert_status),
                cert_thumbprint = COALESCE(excluded.cert_thumbprint, pd_executions.cert_thumbprint),
                failure_stage = COALESCE(excluded.failure_stage, pd_executions.failure_stage),
                root_cause = COALESCE(excluded.root_cause, pd_executions.root_cause),
                http_status = COALESCE(excluded.http_status, pd_executions.http_status),

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

                cert_status,
                cert_thumbprint,
                failure_stage,
                root_cause,
                http_status,

                retry_count,
                event_id,   # first_event_id (set once)
                event_id,   # last_event_id (always updated)
            ),
        )

        conn.commit()
        conn.close()

        logger.info(
            "UPSERT_COMMITTED",
            extra={"requestId": request_id, "eventId": event_id},
        )

    except Exception:
        logger.exception(
            "FAILED_TO_UPSERT_PD_EXECUTION",
            extra={"requestId": request_id, "eventId": event_id},
        )
        raise


# =========================================================
# CERT / FAILURE FIELD MANAGEMENT (USED BY FINDINGS)
# =========================================================

def get_execution_cert_fields(request_id: str) -> dict[str, object] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                cert_status,
                cert_thumbprint,
                failure_stage,
                root_cause,
                http_status
            FROM pd_executions
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_execution_cert_fields(
    *,
    request_id: str,
    cert_status: str | None,
    cert_thumbprint: str | None,
    failure_stage: str | None,
    root_cause: str | None,
    http_status: int | None,
) -> None:
    current = get_execution_cert_fields(request_id)
    if not current:
        return

    cert_rank = {
        None: 0,
        "UNKNOWN": 0,
        "NOT_REPORTED": 0,
        "VALID": 1,
        "INVALID": 2,
        "EXPIRED": 2,
        "UNTRUSTED": 2,
    }

    next_cert_status = current["cert_status"]
    if cert_status is not None and cert_rank.get(cert_status, 0) > cert_rank.get(
        current["cert_status"], 0
    ):
        next_cert_status = cert_status

    next_thumbprint = current["cert_thumbprint"]
    if cert_thumbprint and not current["cert_thumbprint"]:
        next_thumbprint = cert_thumbprint

    next_failure_stage = current["failure_stage"]
    if failure_stage and current["failure_stage"] in (None, "UNKNOWN"):
        next_failure_stage = failure_stage

    next_root_cause = current["root_cause"]
    if root_cause and current["root_cause"] in (None, "UNKNOWN"):
        next_root_cause = root_cause

    next_http_status = current["http_status"]
    if http_status is not None and current["http_status"] is None:
        next_http_status = http_status

    if (
        next_cert_status == current["cert_status"]
        and next_thumbprint == current["cert_thumbprint"]
        and next_failure_stage == current["failure_stage"]
        and next_root_cause == current["root_cause"]
        and next_http_status == current["http_status"]
    ):
        return

    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE pd_executions
            SET
                cert_status = ?,
                cert_thumbprint = ?,
                failure_stage = ?,
                root_cause = ?,
                http_status = ?
            WHERE request_id = ?
            """,
            (
                next_cert_status,
                next_thumbprint,
                next_failure_stage,
                next_root_cause,
                next_http_status,
                request_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def count_executions() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) FROM pd_executions").fetchone()
    conn.close()
    return int(row[0]) if row else 0


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
            ON pd_executions.source_oid = od.oid
        ORDER BY completed_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    return [
        PDExecution(
            requestId=row["request_id"],
            startedAt=row["started_at"],
            completedAt=row["completed_at"],
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
