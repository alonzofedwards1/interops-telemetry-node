import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
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

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def issue_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.auth_session_ttl_seconds)

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO telemetry_sessions (
                user_id,
                token_hash,
                created_at,
                last_activity_at,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, token_hash, now, now, expires_at),
        )
        conn.commit()
    finally:
        conn.close()

    logger.debug(
        "SESSION_CREATED",
        extra={
            "userId": user_id,
            "expiresAt": expires_at.isoformat(),
        },
    )

    return token


def validate_session(token: str) -> int | None:
    if not token:
        return None

    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_id, expires_at, last_activity_at
            FROM telemetry_sessions
            WHERE token_hash = %s
              AND expires_at > NOW()
              AND last_activity_at > NOW() - INTERVAL '30 minutes'
            """,
            (token_hash,),
        ).fetchone()

        if not row:
            return None

        expires_at = row["expires_at"]

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            logger.info(
                "SESSION_EXPIRED",
                extra={"userId": row["user_id"]},
            )
            return None

        conn.execute(
            """
            UPDATE telemetry_sessions
            SET last_activity_at = %s
            WHERE token_hash = %s
            """,
            (now, token_hash),
        )
        conn.commit()

        return row["user_id"]

    finally:
        conn.close()


def clear_session(token: str) -> None:
    if not token:
        return

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

    logger.debug("SESSION_CLEARED")


def verify_totp_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)


def login(username: str, password: str):
    user = repository.get_user_by_username(username)

    if not user:
        logger.warning(
            "AUTH_LOGIN_FAILED_UNKNOWN_USER",
            extra={"username": username},
        )
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

        repository.update_user_password(
            user["id"],
            hash_password(password),
        )

        logger.info(
            "AUTH_LOGIN_LEGACY_HASH_UPGRADED",
            extra={"username": username, "userId": user["id"]},
        )

    if user.get("mfa_enabled"):
        logger.info(
            "AUTH_MFA_REQUIRED",
            extra={"userId": user["id"]},
        )

        return {
            "mfa_required": True,
            "user_id": user["id"],
        }

    token = issue_session(user["id"])

    logger.info(
        "AUTH_LOGIN_SUCCESS",
        extra={"username": username, "userId": user["id"]},
    )

    return {"token": token}

def complete_mfa(user_id: int, code: str) -> str:
    user = repository.get_user_by_id(user_id)

    if not user or not user.get("totp_secret"):
        raise Exception("MFA not configured")

    if not verify_totp_code(user["totp_secret"], code):
        logger.warning(
            "AUTH_MFA_FAILED",
            extra={"userId": user_id},
        )
        raise Exception("Invalid MFA code")

    token = issue_session(user_id)

    logger.info(
        "AUTH_MFA_SUCCESS",
        extra={"userId": user_id},
    )

    return token


def logout(token: str | None):
    if token:
        clear_session(token)