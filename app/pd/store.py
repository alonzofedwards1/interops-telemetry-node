import logging
from typing import List

from app.db.connection import get_connection
from app.pd.models import PDExecution

logger = logging.getLogger(__name__)


def upsert_execution(
    request_id: str,
    started_at: str,
    completed_at: str,
    duration_ms: int,
    outcome: str,
    success: bool,
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
                success
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                duration_ms = excluded.duration_ms,
                outcome = excluded.outcome,
                success = excluded.success
            """,
            (
                request_id,
                started_at,
                completed_at,
                duration_ms,
                outcome,
                1 if success else 0,
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Failed to upsert PD execution")
        raise


def list_executions(limit: int = 500) -> List[PDExecution]:
    try:
        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT
                request_id,
                started_at,
                completed_at,
                duration_ms,
                outcome,
                success
            FROM pd_executions
            ORDER BY completed_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            PDExecution(
                requestId=row["request_id"],
                startedAt=row["started_at"],
                completedAt=row["completed_at"],
                durationMs=row["duration_ms"],
                outcome=row["outcome"],
                success=bool(row["success"]),
            )
            for row in rows
        ]
    except Exception:
        logger.exception("Failed to list PD executions")
        raise


def count_executions() -> int:
    try:
        conn = get_connection()
        cursor = conn.execute("SELECT COUNT(*) as count FROM pd_executions")
        row = cursor.fetchone()
        conn.close()
        return int(row["count"]) if row else 0
    except Exception:
        logger.exception("Failed to count PD executions")
        raise
