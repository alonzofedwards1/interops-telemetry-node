import logging
from pathlib import Path

from app.db.connection import get_connection

logger = logging.getLogger(__name__)


TELEMETRY_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_layer TEXT,
    timestamp_utc TEXT NOT NULL,
    source_channel_id TEXT,
    source_environment TEXT,
    status TEXT,
    duration_ms INTEGER,
    correlation_request_id TEXT,
    cert_status TEXT,
    cert_thumbprint TEXT,
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
    cert_status TEXT DEFAULT 'NOT_REPORTED',
    cert_thumbprint TEXT,
    failure_stage TEXT,
    root_cause TEXT,
    http_status INTEGER,
    first_event_id TEXT,
    last_event_id TEXT
);
"""

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

SESSIONS_TOKEN_HASH_INDEX = """
CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON telemetry_sessions(token_hash);
"""

SESSIONS_EXPIRES_AT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON telemetry_sessions(expires_at);
"""


def _apply_schema(conn, schema_name: str) -> None:
    schema_path = Path(__file__).resolve().parent / schema_name
    if schema_path.exists():
        logger.info("Applying schema from %s", schema_path)
        conn.executescript(schema_path.read_text(encoding="utf-8"))


def run_migrations() -> None:
    try:
        conn = get_connection()
        conn.execute(TELEMETRY_EVENTS_SCHEMA)
        conn.execute(PD_EXECUTIONS_SCHEMA)
        conn.execute(USERS_SCHEMA)
        conn.execute(SESSIONS_SCHEMA)
        conn.execute(SESSIONS_TOKEN_HASH_INDEX)
        conn.execute(SESSIONS_EXPIRES_AT_INDEX)

        _apply_schema(conn, "schema_findings.sql")
        _apply_schema(conn, "schema_oid_directory.sql")

        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Failed to run database migrations")
        raise
