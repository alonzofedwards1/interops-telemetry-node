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
    logger.info(
        "SESSION_ISSUE_START",
        extra={
            "user_id": user_id,
            "expires_at": expires_at,
            "token_hash_prefix": token_hash[:8],
        },
    )

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
        logger.info(
            "SESSION_ISSUE_COMMIT",
            extra={"user_id": user_id, "expires_at": expires_at},
        )
    finally:
        conn.close()

    return token


def validate_session(token: str) -> int | None:
    logger.info(
        "SESSION_VALIDATE_START",
        extra={
            "token_present": bool(token),
            "token_len": len(token) if token else 0,
        },
    )
    token_hash = _hash_token(token)
    logger.info(
        "SESSION_HASH",
        extra={"hash_prefix": token_hash[:8]},
    )
    now_utc = datetime.utcnow()

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_id, expires_at
            FROM telemetry_sessions
            WHERE token_hash = %s
              AND expires_at > NOW()
            """,
            (token_hash,),
        ).fetchone()
        logger.info("SESSION_DB_RESULT", extra={"found": bool(row)})
        logger.info(
            "SESSION_EXPIRY_CHECK",
            extra={
                "expires_at": str(row["expires_at"]) if row else None,
                "now": str(now_utc),
            },
        )
        logger.info(
            "SESSION_VALIDATE_RESULT",
            extra={"status": "valid" if row else "not_found_or_expired"},
        )
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
    logger.info("LOGIN_ATTEMPT", extra={"username": username})
    user = repository.get_user_by_username(username)

    if not user:
        logger.info("LOGIN_USER_LOOKUP", extra={"username": username, "found": False})
        logger.warning("AUTH_LOGIN_FAILED_UNKNOWN_USER", extra={"username": username})
        raise Exception("Invalid credentials")

    logger.info(
        "LOGIN_USER_LOOKUP",
        extra={"username": username, "found": True, "user_id": user["id"]},
    )
    try:
        if not verify_password(password, user["password_hash"]):
            logger.info(
                "LOGIN_PASSWORD_VALIDATION",
                extra={"user_id": user["id"], "valid": False},
            )
            logger.warning(
                "AUTH_LOGIN_FAILED_BAD_PASSWORD",
                extra={"username": username, "userId": user["id"]},
            )
            raise Exception("Invalid credentials")
        logger.info(
            "LOGIN_PASSWORD_VALIDATION",
            extra={"user_id": user["id"], "valid": True},
        )

    except (UnknownHashError, ValueError):
        logger.info(
            "LOGIN_PASSWORD_VALIDATION_FALLBACK",
            extra={"user_id": user["id"], "strategy": "legacy_sha256"},
        )
        if not verify_legacy_sha256_password(
                password,
                user["password_hash"],
                settings.auth_password_salt,
        ):
            logger.info(
                "LOGIN_PASSWORD_VALIDATION",
                extra={"user_id": user["id"], "valid": False, "strategy": "legacy_sha256"},
            )
            logger.warning(
                "AUTH_LOGIN_FAILED_INVALID_HASH",
                extra={"username": username, "userId": user["id"]},
            )
            raise Exception("Invalid credentials")
        logger.info(
            "LOGIN_PASSWORD_VALIDATION",
            extra={"user_id": user["id"], "valid": True, "strategy": "legacy_sha256"},
        )

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
    logger.info(
        "SESSION_CREATED",
        extra={"user_id": user["id"], "token_len": len(token)},
    )
    return token


def logout(token: str | None):
    if token:
        clear_session(token)
