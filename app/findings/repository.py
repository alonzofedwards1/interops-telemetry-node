import logging
from datetime import datetime, timezone
from typing import Any, Optional

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


# ============================================================
# LIST FINDINGS (WITH ORGANIZATION RESOLUTION)
# ============================================================

def list_findings(
    *,
    limit: Optional[int] = None,   # 🔥 IMPORTANT
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
    sort = f"f.{sort}" if sort in _ALLOWED_SORT_FIELDS else "f.created_at"
    order = order if order in _ALLOWED_ORDER else "desc"

    where_clauses: list[str] = []
    params: list[Any] = []

    if severity:
        where_clauses.append("f.severity = ?")
        params.append(severity)
    if status:
        where_clauses.append("f.status = ?")
        params.append(status)
    if category:
        where_clauses.append("f.category = ?")
        params.append(category)
    if execution_type:
        where_clauses.append("f.execution_type = ?")
        params.append(execution_type)
    if execution_id:
        where_clauses.append("f.execution_id = ?")
        params.append(execution_id)
    if q:
        where_clauses.append("(f.summary LIKE ? OR f.technical_detail LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT
            f.id,
            f.execution_id,
            f.execution_type,
            f.severity,
            f.category,
            f.summary,
            f.technical_detail,
            f.recommended_action,
            f.status,
            f.first_seen_at,
            f.last_seen_at,
            f.created_at,
            f.updated_at,

            e.source_oid AS source_oid,
            od.organization_name AS organization_name

        FROM findings f
        JOIN pd_executions e
            ON f.execution_id = e.request_id
        LEFT JOIN oid_directory od
            ON e.source_oid = od.oid

        {where_sql}
        ORDER BY {sort} {order}
    """

    # 🔥 CRITICAL FIX: only apply LIMIT if provided
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed list_findings query")
        raise
    finally:
        conn.close()


# ============================================================
# GET FINDING BY ID
# ============================================================

def get_finding_by_id(finding_id: str) -> dict[str, Any] | None:
    query = """
        SELECT
            f.id,
            f.execution_id,
            f.execution_type,
            f.severity,
            f.category,
            f.summary,
            f.technical_detail,
            f.recommended_action,
            f.status,
            f.first_seen_at,
            f.last_seen_at,
            f.created_at,
            f.updated_at,

            e.source_oid AS source_oid,
            od.organization_name AS organization_name

        FROM findings f
        JOIN pd_executions e
            ON f.execution_id = e.request_id
        LEFT JOIN oid_directory od
            ON e.source_oid = od.oid
        WHERE f.id = ?
    """

    conn = get_connection()
    try:
        row = conn.execute(query, (finding_id,)).fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("Failed get_finding_by_id query")
        raise
    finally:
        conn.close()


# ============================================================
# FINDING ID RESOLUTION
# ============================================================

def find_finding_ids_by_signature(
    *,
    execution_id: str | None,
    execution_type: str,
    severity: str,
    category: str,
    summary: str,
) -> list[str]:
    if execution_id is None:
        return []

    query = """
        SELECT id
        FROM findings
        WHERE execution_id = ?
          AND execution_type = ?
          AND severity = ?
          AND category = ?
          AND summary = ?
        ORDER BY created_at ASC
    """

    conn = get_connection()
    try:
        rows = conn.execute(
            query,
            (execution_id, execution_type, severity, category, summary),
        ).fetchall()
        return [row["id"] for row in rows]
    except Exception:
        logger.exception("Failed find_finding_ids_by_signature query")
        raise
    finally:
        conn.close()


def replace_finding_id(*, current_id: str, new_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE findings
            SET id = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_id, _utc_now(), current_id),
        )
        conn.commit()
    except Exception:
        logger.exception("Failed replace_finding_id query")
        raise
    finally:
        conn.close()


def delete_finding_by_id(finding_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            DELETE FROM findings
            WHERE id = ?
            """,
            (finding_id,),
        )
        conn.commit()
    except Exception:
        logger.exception("Failed delete_finding_by_id query")
        raise
    finally:
        conn.close()


# ============================================================
# COUNTS (AUTHORITATIVE INVENTORY)
# ============================================================

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

    conn = get_connection()
    try:
        row = conn.execute(query, params).fetchone()
        return {k: int(row[k] or 0) for k in row.keys()} if row else {}
    except Exception:
        logger.exception("Failed get_findings_counts query")
        raise
    finally:
        conn.close()


# ============================================================
# WRITE OPERATIONS
# ============================================================

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
        return get_finding_by_id(finding_id)
    except Exception:
        logger.exception("Failed update_finding_status query")
        raise
    finally:
        conn.close()
