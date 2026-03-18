import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta

from passlib.exc import UnknownHashError

from app.auth import repository
from app.auth.security import (
    hash_password,
    verify_password,
    verify_legacy_sha256_password,
)
from app.config.settings import get_settings
from app.db.connection import get_connection

settings = get_settings()
logger = logging.getLogger(__name__)


# ---------------------------
# SESSION HELPERS
# ---------------------------

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = int(time.time()) + settings.auth_session_ttl_seconds

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


# ---------------------------
# AUTH LOGIC
# ---------------------------

def login(username: str, password: str) -> str:
    user = repository.get_user_by_username(username)

    if not user:
        logger.warning("AUTH_LOGIN_FAILED_UNKNOWN_USER", extra={"username": username})
        raise Exception("Invalid credentials")

    try:
        if not verify_password(password, user["password_hash"]):
            logger.warning(
                "AUTH_LOGIN_FAILED_BAD_PASSWORD",
                extra={"username": username, "userId": user["id"]},
            )
            raise Exception("Invalid credentials")

    except (UnknownHashError, ValueError):
        if not verify_legacy_sha256_password(
                password,
                user["password_hash"],
                settings.auth_password_salt,
        ):
            logger.warning(
                "AUTH_LOGIN_FAILED_INVALID_HASH",
                extra={"username": username, "userId": user["id"]},
            )
            raise Exception("Invalid credentials")

        # upgrade legacy password
        repository.update_user_password(
            user["id"],
            hash_password(password),
        )

        logger.info(
            "AUTH_LOGIN_LEGACY_HASH_UPGRADED",
            extra={"username": username, "userId": user["id"]},
        )

    token = issue_session(user["id"])
    return token


def logout(token: str | None):
    if token:
        clear_session(token)
