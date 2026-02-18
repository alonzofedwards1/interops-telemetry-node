import logging
from pathlib import Path

from app.db.connection import get_connection

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Apply PostgreSQL schema migrations."""

    schema_path = Path(__file__).resolve().parent / "schema_postgres.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Missing PostgreSQL schema file: {schema_path}")

    try:
        conn = get_connection()
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Failed to run database migrations")
        raise
