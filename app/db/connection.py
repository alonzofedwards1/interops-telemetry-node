import sqlite3

from app.config.settings import get_settings

settings = get_settings()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.telemetry_db_path)
    conn.row_factory = sqlite3.Row
    return conn
