import logging

from fastapi import HTTPException, Request

from app.auth.service import validate_session
from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def require_auth(request: Request) -> int:
    cookies = request.cookies or {}
    logger.info(
        "AUTH_REQUIRE_COOKIES_RECEIVED",
        extra={
            "cookie_keys": list(cookies.keys()),
            "cookie_count": len(cookies),
        },
    )

    token = request.cookies.get(settings.auth_cookie_name)
    logger.info(
        "AUTH_REQUIRE_TOKEN_EXTRACTED",
        extra={
            "token_present": bool(token),
            "token_len": len(token) if token else 0,
        },
    )

    if not token:
        logger.warning(
            "AUTH_REQUIRE_FAILED",
            extra={"reason": "missing_auth_cookie"},
        )
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = validate_session(token)
    if not user_id:
        logger.warning(
            "AUTH_REQUIRE_FAILED",
            extra={"reason": "invalid_or_expired_session"},
        )
        raise HTTPException(status_code=401, detail="Invalid session")

    logger.info("AUTH_REQUIRE_SUCCESS", extra={"user_id": user_id})
    return user_id
