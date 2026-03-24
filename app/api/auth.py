import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.auth import repository
from app.auth import service as auth_service
from app.auth.models import LoginRequest
from app.auth.totp import verify_totp
from app.config.settings import get_settings
from app.core.rate_limiter import limiter
from app.services.login_attempt_service import (
    get_remaining_lock_time,
    is_locked,
    record_failure,
    reset_attempts,
)

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()
logger = logging.getLogger(__name__)


def _is_secure_cookie() -> bool:
    return settings.environment.lower() in {"prod", "production"}


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=_is_secure_cookie(),
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest, response: Response):
    username = payload.username

    logger.info("AUTH_LOGIN_ATTEMPT", extra={"username": username})

    if is_locked(username):
        remaining = get_remaining_lock_time(username)
        return JSONResponse(
            status_code=423,
            content={
                "error": {
                    "code": "ACCOUNT_LOCKED",
                    "message": f"Try again in {remaining} seconds",
                }
            },
        )

    try:
        user = auth_service.verify_credentials(username, payload.password)
    except Exception:
        record_failure(username)
        logger.warning("AUTH_LOGIN_FAILED", extra={"username": username})
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid username or password",
                }
            },
        )

    reset_attempts(username)

    if user.get("totp_secret"):
        return {
            "mfaRequired": True,
            "username": username,
        }

    token = auth_service.create_session(user["id"])
    _set_auth_cookie(response, token)

    logger.info(
        "AUTH_LOGIN_SUCCESS",
        extra={"username": username, "userId": user["id"]},
    )

    return {"success": True}


@router.post("/mfa")
async def verify_mfa(payload: dict, response: Response):
    username = payload.get("username")
    code = payload.get("code")

    if not username or not code:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Username and code required",
                }
            },
        )

    user = repository.get_user_by_username(username)

    if not user or not user.get("totp_secret"):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "MFA_NOT_SETUP",
                    "message": "MFA not enabled",
                }
            },
        )

    if not verify_totp(user["totp_secret"], code):
        logger.warning("AUTH_MFA_FAILED", extra={"username": username})
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "INVALID_MFA_CODE",
                    "message": "Invalid authentication code",
                }
            },
        )

    token = auth_service.create_session(user["id"])
    _set_auth_cookie(response, token)

    logger.info("AUTH_MFA_SUCCESS", extra={"username": username, "userId": user["id"]})

    return {"success": True}


@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(settings.auth_cookie_name)

    auth_service.clear_session(token)

    response = JSONResponse(status_code=204, content={})
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_is_secure_cookie(),
    )

    return response


@router.get("/me")
async def me(request: Request):
    token = request.cookies.get(settings.auth_cookie_name)
    user_id = auth_service.validate_session(token)

    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    user = repository.get_user_by_id(user_id)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return {
        "id": str(user["id"]),
        "email": user.get("email", ""),
        "role": user.get("role", ""),
    }
