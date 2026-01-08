import logging

from app.db.connection import get_connection

logger = logging.getLogger(__name__)


PD_EXECUTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pd_executions (
    request_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    success INTEGER NOT NULL
);
"""


def run_migrations() -> None:
    try:
        conn = get_connection()
        conn.execute(PD_EXECUTIONS_SCHEMA)
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Failed to run database migrations")
        raise
