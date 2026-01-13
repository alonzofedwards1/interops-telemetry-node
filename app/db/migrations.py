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
    source_oid TEXT,
    target_oid TEXT,
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
    source_oid TEXT,
    target_oid TEXT,
    first_event_id TEXT,
    last_event_id TEXT
);
"""


def _apply_schema(conn, schema_name: str) -> None:
    schema_path = Path(__file__).resolve().parent / schema_name
    if schema_path.exists():
        logger.info("Applying schema from %s", schema_path)
        conn.executescript(schema_path.read_text(encoding="utf-8"))


def _add_column(conn, table: str, column: str, column_type: str) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
    except Exception:
        logger.debug("Column %s.%s already exists", table, column)


def run_migrations() -> None:
    try:
        conn = get_connection()
        conn.execute(TELEMETRY_EVENTS_SCHEMA)
        conn.execute(PD_EXECUTIONS_SCHEMA)

        _add_column(conn, "telemetry_events", "source_oid", "TEXT")
        _add_column(conn, "telemetry_events", "target_oid", "TEXT")
        _add_column(conn, "pd_executions", "source_oid", "TEXT")
        _add_column(conn, "pd_executions", "target_oid", "TEXT")

        _apply_schema(conn, "schema_findings.sql")
        _apply_schema(conn, "schema_oid_directory.sql")

        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Failed to run database migrations")
        raise
