import logging
import re
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
_db_url_logged = False

_PLACEHOLDER_PATTERN = re.compile(r"\?")


class PostgresConnection:
    """Thin compatibility wrapper exposing a sqlite-like API over psycopg2."""

    def __init__(self, database_url: str) -> None:
        self._conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)

    def cursor(self):
        return self._conn.cursor()

    def execute(self, query: str, params: tuple[Any, ...] | list[Any] | None = None):
        cursor = self._conn.cursor()
        normalized_query = _PLACEHOLDER_PATTERN.sub("%s", query)
        cursor.execute(normalized_query, params or ())
        return cursor

    def executescript(self, script: str) -> None:
        cursor = self._conn.cursor()
        cursor.execute(script)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()



def get_connection() -> PostgresConnection:
    global _db_url_logged
    if not _db_url_logged:
        logger.info("Telemetry DB url: %s", settings.database_url)
        _db_url_logged = True

    return PostgresConnection(settings.database_url)
