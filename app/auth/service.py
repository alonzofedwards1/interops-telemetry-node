import hashlib
import secrets
import time

from app.config.settings import get_settings
from app.db.connection import get_connection

settings = get_settings()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(user_id: int) -> tuple[str, int]:
    token = secrets.token_hex(32)
    token_hash = hash_token(token)
    expires_at = int(time.time()) + settings.auth_session_ttl_seconds

    conn = get_connection()
    conn.execute(
        "INSERT INTO telemetry_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, expires_at),
    )
    conn.commit()
    conn.close()

    return token, expires_at


def clear_session(token: str | None) -> None:
    if not token:
        return

    token_hash = hash_token(token)
    conn = get_connection()
    conn.execute("DELETE FROM telemetry_sessions WHERE token_hash = ?", (token_hash,))
    conn.commit()
    conn.close()
