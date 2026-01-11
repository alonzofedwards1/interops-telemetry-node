import logging
from pathlib import Path

from app.db.connection import get_connection

logger = logging.getLogger(__name__)


TELEMETRY_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    source_channel_id TEXT,
    source_environment TEXT,
    status TEXT,
    duration_ms INTEGER,
    correlation_request_id TEXT,
    raw_payload TEXT
);
"""


PD_EXECUTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pd_executions (
    request_id TEXT PRIMARY KEY,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    outcome TEXT,
    source_channel_id TEXT,
    source_environment TEXT,
    first_event_id TEXT,
    last_event_id TEXT
);
"""


def run_migrations() -> None:
    try:
        conn = get_connection()
        conn.execute(TELEMETRY_EVENTS_SCHEMA)
        conn.execute(PD_EXECUTIONS_SCHEMA)

        findings_schema_path = Path(__file__).resolve().parent / "schema_findings.sql"
        if findings_schema_path.exists():
            logger.info("Applying findings schema from %s", findings_schema_path)
            conn.executescript(findings_schema_path.read_text(encoding="utf-8"))

        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Failed to run database migrations")
        raise
