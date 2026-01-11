import logging
from typing import List

from app.db.connection import get_connection
from app.pd.models import PDExecution

logger = logging.getLogger(__name__)


def upsert_execution(
    *,
    request_id: str,
    event_id: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    duration_ms: int | None = None,
    outcome: str | None = None,
    source_channel_id: str | None = None,
    source_environment: str | None = None,
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
                source_channel_id,
                source_environment,
                first_event_id,
                last_event_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                started_at = COALESCE(pd_executions.started_at, excluded.started_at),
                completed_at = COALESCE(excluded.completed_at, pd_executions.completed_at),
                duration_ms = COALESCE(excluded.duration_ms, pd_executions.duration_ms),
                outcome = COALESCE(excluded.outcome, pd_executions.outcome),
                source_channel_id = COALESCE(excluded.source_channel_id, pd_executions.source_channel_id),
                source_environment = COALESCE(excluded.source_environment, pd_executions.source_environment),
                last_event_id = excluded.last_event_id
            """,
            (
                request_id,
                started_at,
                completed_at,
                duration_ms,
                outcome,
                source_channel_id,
                source_environment,
                event_id,
                event_id,
            ),
        )

        conn.commit()
        conn.close()

        logger.info("PD execution upserted", extra={"requestId": request_id})

    except Exception:
        logger.exception("Failed to upsert PD execution")
        raise


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
            source_environment
        FROM pd_executions
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
        )
        for row in rows
    ]
