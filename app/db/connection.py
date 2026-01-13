import logging
import sqlite3
from pathlib import Path

from app.config.settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)
_db_path_logged = False


def get_connection() -> sqlite3.Connection:
    global _db_path_logged
    db_path = Path(settings.telemetry_db_path)
    if not _db_path_logged:
        logger.info("Telemetry DB path: %s", db_path)
        _db_path_logged = True

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
