import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from passlib.exc import UnknownHashError

from app.auth import repository
from app.auth.security import (
    hash_password,
    verify_legacy_sha256_password,
    verify_password,
)
from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

SESSION_IDLE_TIMEOUT_SECONDS = 30 * 60


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_credentials(username: str, password: str):
    user = repository.get_user_by_username(username)

    if not user:
        raise ValueError("Invalid credentials")

    stored_hash = user.get("password_hash")
    if not stored_hash:
        raise ValueError("Invalid credentials")

    try:
        valid = verify_password(password, stored_hash)
    except (UnknownHashError, ValueError):
        valid = False

    if not valid:
        if not verify_legacy_sha256_password(
            password,
            stored_hash,
            settings.auth_password_salt,
        ):
            raise ValueError("Invalid credentials")

        repository.update_user_password(user["id"], hash_password(password))
        logger.info(
            "AUTH_LOGIN_LEGACY_HASH_UPGRADED",
            extra={"username": username, "userId": user["id"]},
        )

    return user


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)

    now = _utc_now()
    expires_at = now + timedelta(seconds=settings.auth_session_ttl_seconds)

    repository.insert_session(
        user_id=user_id,
        token_hash=token_hash,
        created_at=now,
        last_activity_at=now,
        expires_at=expires_at,
    )

    return token


def validate_session(token: str) -> int | None:
    if not token:
        return None

    now = _utc_now()
    token_hash = _hash_token(token)
    session_row = repository.get_session_by_token_hash(token_hash)

    if not session_row:
        return None

    expires_at = _coerce_utc(session_row["expires_at"])
    last_activity_at = _coerce_utc(session_row["last_activity_at"])

    if expires_at <= now:
        logger.info("SESSION_EXPIRED", extra={"userId": session_row["user_id"]})
        return None

    if now - last_activity_at > timedelta(seconds=SESSION_IDLE_TIMEOUT_SECONDS):
        logger.info("SESSION_IDLE_TIMEOUT", extra={"userId": session_row["user_id"]})
        return None

    repository.update_session_activity(token_hash, now)
    return int(session_row["user_id"])


def clear_session(token: str) -> None:
    if not token:
        return

    token_hash = _hash_token(token)
    repository.delete_session_by_token_hash(token_hash)


def logout(token: str | None):
    if token:
        clear_session(token)


# TODO: implement periodic cleanup for expired sessions.
