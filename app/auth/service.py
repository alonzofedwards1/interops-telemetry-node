import hashlib
import secrets
from datetime import datetime, timedelta

from app.config.settings import get_settings
from app.db.connection import get_connection

settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.utcnow() + timedelta(seconds=settings.auth_session_ttl_seconds)

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO telemetry_sessions (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, token_hash, expires_at),
        )
        conn.commit()
    finally:
        conn.close()

    return token


def validate_session(token: str) -> int | None:
    token_hash = _hash_token(token)

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_id
            FROM telemetry_sessions
            WHERE token_hash = %s
              AND expires_at > NOW()
            """,
            (token_hash,),
        ).fetchone()
        return row["user_id"] if row else None
    finally:
        conn.close()


def clear_session(token: str) -> None:
    token_hash = _hash_token(token)

    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM telemetry_sessions WHERE token_hash = %s",
            (token_hash,),
        )
        conn.commit()
    finally:
        conn.close()
