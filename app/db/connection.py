import logging
import re
from typing import Any

import asyncpg
import psycopg2
from psycopg2.extras import DictCursor

from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
_db_url_logged = False
_async_pool: asyncpg.Pool | None = None

_PLACEHOLDER_PATTERN = re.compile(r"\?")


def _normalize_database_url(database_url: str) -> str:
    """Accept SQLAlchemy-style URLs in DB connection clients."""

    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return database_url


class PostgresConnection:
    """Thin compatibility wrapper exposing a sqlite-like API over psycopg2."""

    def __init__(self, database_url: str) -> None:
        self._conn = psycopg2.connect(_normalize_database_url(database_url), cursor_factory=DictCursor)

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


async def get_async_pool() -> asyncpg.Pool:
    global _async_pool

    if _async_pool is None:
        _async_pool = await asyncpg.create_pool(
            dsn=_normalize_database_url(settings.database_url),
            min_size=1,
            max_size=10,
        )

    return _async_pool


async def get_db() -> asyncpg.Pool:
    return await get_async_pool()


def get_connection() -> PostgresConnection:
    global _db_url_logged
    if not _db_url_logged:
        logger.info("Telemetry DB url: %s", settings.database_url)
        _db_url_logged = True

    return PostgresConnection(settings.database_url)
