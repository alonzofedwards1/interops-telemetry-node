import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection

logger = logging.getLogger(__name__)

_ALLOWED_SORT_FIELDS = {
    "created_at",
    "updated_at",
    "severity",
    "status",
    "category",
    "last_seen_at",
    "first_seen_at",
}

_ALLOWED_ORDER = {"asc", "desc"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def list_findings(
    *,
    limit: int = 50,
    offset: int = 0,
    severity: str | None = None,
    status: str | None = None,
    category: str | None = None,
    execution_type: str | None = None,
    execution_id: str | None = None,
    q: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> list[dict[str, Any]]:
    if sort not in _ALLOWED_SORT_FIELDS:
        sort = "created_at"
    if order not in _ALLOWED_ORDER:
        order = "desc"

    where_clauses = []
    params: list[Any] = []

    if severity:
        where_clauses.append("severity = ?")
        params.append(severity)
    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if category:
        where_clauses.append("category = ?")
        params.append(category)
    if execution_type:
        where_clauses.append("execution_type = ?")
        params.append(execution_type)
    if execution_id:
        where_clauses.append("execution_id = ?")
        params.append(execution_id)
    if q:
        where_clauses.append("(summary LIKE ? OR technical_detail LIKE ?)")
        like_value = f"%{q}%"
        params.extend([like_value, like_value])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT
            id,
            execution_id,
            execution_type,
            severity,
            category,
            summary,
            technical_detail,
            recommended_action,
            status,
            first_seen_at,
            last_seen_at,
            created_at,
            updated_at
        FROM findings
        {where_sql}
        ORDER BY {sort} {order}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    logger.debug(
        "list_findings",
        extra={"params": params, "sort": sort, "order": order},
    )

    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed list_findings query")
        raise
    finally:
        conn.close()


def get_finding_by_id(finding_id: str) -> dict[str, Any] | None:
    logger.debug("get_finding_by_id", extra={"id": finding_id})
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                id,
                execution_id,
                execution_type,
                severity,
                category,
                summary,
                technical_detail,
                recommended_action,
                status,
                first_seen_at,
                last_seen_at,
                created_at,
                updated_at
            FROM findings
            WHERE id = ?
            """,
            (finding_id,),
        ).fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("Failed get_finding_by_id query")
        raise
    finally:
        conn.close()


def get_findings_counts(
    *,
    severity: str | None = None,
    status: str | None = None,
    execution_type: str | None = None,
) -> dict[str, int]:
    where_clauses = []
    params: list[Any] = []

    if severity:
        where_clauses.append("severity = ?")
        params.append(severity)
    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if execution_type:
        where_clauses.append("execution_type = ?")
        params.append(execution_type)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN severity = 'warning' THEN 1 ELSE 0 END) AS warnings,
            SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical,
            SUM(CASE WHEN severity = 'info' THEN 1 ELSE 0 END) AS info,
            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open,
            SUM(CASE WHEN status = 'acknowledged' THEN 1 ELSE 0 END) AS acknowledged,
            SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS resolved
        FROM findings
        {where_sql}
    """

    logger.debug("get_findings_counts", extra={"params": params})

    conn = get_connection()
    try:
        row = conn.execute(query, params).fetchone()
        if not row:
            return {
                "total": 0,
                "warnings": 0,
                "critical": 0,
                "info": 0,
                "open": 0,
                "acknowledged": 0,
                "resolved": 0,
            }
        return {
            "total": int(row["total"] or 0),
            "warnings": int(row["warnings"] or 0),
            "critical": int(row["critical"] or 0),
            "info": int(row["info"] or 0),
            "open": int(row["open"] or 0),
            "acknowledged": int(row["acknowledged"] or 0),
            "resolved": int(row["resolved"] or 0),
        }
    except Exception:
        logger.exception("Failed get_findings_counts query")
        raise
    finally:
        conn.close()


def add_or_update_finding(
    *,
    id: str,
    execution_id: str | None,
    execution_type: str,
    severity: str,
    category: str,
    summary: str,
    technical_detail: str | None,
    recommended_action: str | None,
    status: str = "open",
) -> None:
    now = _utc_now()
    logger.debug(
        "add_or_update_finding",
        extra={
            "id": id,
            "execution_id": execution_id,
            "execution_type": execution_type,
            "severity": severity,
            "status": status,
        },
    )
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO findings (
                id,
                execution_id,
                execution_type,
                severity,
                category,
                summary,
                technical_detail,
                recommended_action,
                status,
                first_seen_at,
                last_seen_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                execution_id = excluded.execution_id,
                execution_type = excluded.execution_type,
                severity = excluded.severity,
                category = excluded.category,
                summary = excluded.summary,
                technical_detail = COALESCE(excluded.technical_detail, findings.technical_detail),
                recommended_action = COALESCE(excluded.recommended_action, findings.recommended_action),
                status = excluded.status,
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at
            """,
            (
                id,
                execution_id,
                execution_type,
                severity,
                category,
                summary,
                technical_detail,
                recommended_action,
                status,
                now,
                now,
                now,
            ),
        )
        conn.commit()
    except Exception:
        logger.exception("Failed add_or_update_finding query")
        raise
    finally:
        conn.close()


def update_finding_status(*, finding_id: str, status: str) -> dict[str, Any] | None:
    now = _utc_now()
    logger.debug("update_finding_status", extra={"id": finding_id, "status": status})
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE findings
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, now, finding_id),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT
                id,
                execution_id,
                execution_type,
                severity,
                category,
                summary,
                technical_detail,
                recommended_action,
                status,
                first_seen_at,
                last_seen_at,
                created_at,
                updated_at
            FROM findings
            WHERE id = ?
            """,
            (finding_id,),
        ).fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("Failed update_finding_status query")
        raise
    finally:
        conn.close()
