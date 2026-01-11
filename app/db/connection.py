import sqlite3
import logging

from app.config.settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.telemetry_db_path)
    conn.row_factory = sqlite3.Row
    return conn



logger.warning("TELEMETRY DB PATH IN USE: %s", settings.telemetry_db_path)
