import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection

logger = logging.getLogger(__name__)

_ALLOWED_SORT_FIELDS = {
    "last_seen_at",
    "oid",
    "status",
}

_ALLOWED_ORDER = {"asc", "desc"}

_STATUS_TRANSITIONS = {
    "UNKNOWN": {"PENDING"},
    "PENDING": {"ACTIVE"},
    "ACTIVE": {"DEPRECATED"},
    "DEPRECATED": {"ACTIVE"},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def register_observed_oid(oid: str, org_name: str | None = None) -> None:
    now = _utc_now()
    logger.debug("register_observed_oid", extra={"oid": oid, "org_name": org_name})
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO oid_directory (
                oid,
                organization_name,
                status,
                first_seen_at,
                last_seen_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, 'UNKNOWN', ?, ?, ?, ?)
            ON CONFLICT(oid) DO UPDATE SET
                organization_name = COALESCE(oid_directory.organization_name, excluded.organization_name),
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at
            """,
            (oid, org_name, now, now, now, now),
        )
        conn.commit()
    except Exception:
        logger.exception("Failed to register observed OID")
        raise
    finally:
        conn.close()


def list_oids(
    *,
    status: str | None = None,
    confidence: str | None = None,
    sort: str = "last_seen_at",
    order: str = "desc",
) -> list[dict[str, Any]]:
    if sort not in _ALLOWED_SORT_FIELDS:
        sort = "last_seen_at"
    if order not in _ALLOWED_ORDER:
        order = "desc"

    where_clauses = []
    params: list[Any] = []

    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if confidence:
        confidence_upper = confidence.upper()
        if confidence_upper == "HIGH":
            where_clauses.append("confidence_score >= 0.75")
        elif confidence_upper == "MEDIUM":
            where_clauses.append("confidence_score >= 0.4 AND confidence_score < 0.75")
        elif confidence_upper == "LOW":
            where_clauses.append("confidence_score < 0.4 OR confidence_score IS NULL")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT
            oid,
            organization_name,
            status,
            confidence_score,
            first_seen_at,
            last_seen_at
        FROM oid_directory
        {where_sql}
        ORDER BY {sort} {order}
    """

    logger.debug("list_oids", extra={"params": params, "sort": sort, "order": order})
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed list_oids query")
        raise
    finally:
        conn.close()


def get_oid(oid: str) -> dict[str, Any] | None:
    logger.debug("get_oid", extra={"oid": oid})
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                oid,
                organization_name,
                status,
                confidence_score,
                first_seen_at,
                last_seen_at
            FROM oid_directory
            WHERE oid = ?
            """,
            (oid,),
        ).fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("Failed get_oid query")
        raise
    finally:
        conn.close()


def _pd_has_oid_columns(conn) -> bool:
    columns = conn.execute("PRAGMA table_info(pd_executions)").fetchall()
    if not columns:
        return False
    column_names = {row[1] for row in columns}
    return "source_oid" in column_names and "target_oid" in column_names


def get_oid_usage_counts(oid: str) -> dict[str, int]:
    logger.debug("get_oid_usage_counts", extra={"oid": oid})
    conn = get_connection()
    try:
        if not _pd_has_oid_columns(conn):
            return {"pd": 0, "qd": 0, "rd": 0, "xds": 0}
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM pd_executions
            WHERE source_oid = ? OR target_oid = ?
            """,
            (oid, oid),
        ).fetchone()
        pd_count = int(row["count"] or 0) if row else 0
        return {"pd": pd_count, "qd": 0, "rd": 0, "xds": 0}
    except Exception:
        logger.exception("Failed get_oid_usage_counts query")
        raise
    finally:
        conn.close()


def update_oid_governance(
    *,
    oid: str,
    action: str,
    owner_org: str | None,
    reviewed_by: str | None,
) -> dict[str, Any] | None:
    action_upper = action.upper()
    logger.debug(
        "update_oid_governance",
        extra={"oid": oid, "action": action_upper, "owner_org": owner_org},
    )

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM oid_directory WHERE oid = ?",
            (oid,),
        ).fetchone()
        if not row:
            return None

        current_status = row["status"]
        now = _utc_now()

        if action_upper == "ASSIGN_ORG":
            conn.execute(
                """
                UPDATE oid_directory
                SET organization_name = ?, reviewed_by = ?, reviewed_at = ?, updated_at = ?
                WHERE oid = ?
                """,
                (owner_org, reviewed_by, now, now, oid),
            )
        else:
            target_status = None
            if action_upper == "APPROVE":
                target_status = "ACTIVE"
            elif action_upper == "REJECT":
                target_status = "PENDING"
            elif action_upper == "DEPRECATE":
                target_status = "DEPRECATED"
            elif action_upper == "REACTIVATE":
                target_status = "ACTIVE"

            if not target_status:
                raise ValueError("Unknown governance action")

            allowed = _STATUS_TRANSITIONS.get(current_status, set())

            if target_status not in allowed:
                logger.error(
                    "INVALID_GOVERNANCE_TRANSITION",
                    extra={
                        "oid": oid,
                        "current_status": current_status,
                        "attempted_action": action_upper,
                        "target_status": target_status,
                        "allowed_targets": list(allowed),
                        "reviewed_by": reviewed_by,
                    },
                )
                raise ValueError("Invalid status transition")

            conn.execute(
                """
                UPDATE oid_directory
                SET status = ?, organization_name = COALESCE(?, organization_name),
                    reviewed_by = ?, reviewed_at = ?, updated_at = ?
                WHERE oid = ?
                """,
                (target_status, owner_org, reviewed_by, now, now, oid),
            )

        conn.commit()

        updated = conn.execute(
            """
            SELECT
                oid,
                organization_name,
                status,
                confidence_score,
                first_seen_at,
                last_seen_at
            FROM oid_directory
            WHERE oid = ?
            """,
            (oid,),
        ).fetchone()
        return dict(updated) if updated else None
    except Exception:
        logger.exception("Failed update_oid_governance query")
        raise
    finally:
        conn.close()
