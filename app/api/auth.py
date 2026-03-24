import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_auth
from app.auth.models import LoginRequest, LoginResponse
from app.auth import service as auth_service
from app.auth import repository
from app.config.settings import get_settings
from app.core.rate_limiter import limiter
from app.auth.totp import verify_totp

# 🔒 TEMP: disable lock system for debugging
# from app.services.login_attempt_service import (
#     is_locked,
#     record_failure,
#     reset_attempts,
#     get_remaining_lock_time,
# )

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------
@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest, response: Response):
    username = payload.username
    password = payload.password

    logger.info("AUTH_LOGIN_ATTEMPT", extra={"username": username})

    # 🔍 DEBUG INPUT (REMOVE LATER)
    logger.info(
        "LOGIN_DEBUG",
        extra={
            "username": username,
            "password": password,
            "password_length": len(password) if password else None,
        },
    )

    # 🔒 LOCK CHECK (DISABLED FOR NOW)
    # if is_locked(username):
    #     remaining = get_remaining_lock_time(username)
    #     return JSONResponse(
    #         status_code=423,
    #         content={
    #             "error": {
    #                 "code": "ACCOUNT_LOCKED",
    #                 "message": f"Account locked. Try again in {remaining} seconds.",
    #             }
    #         },
    #     )

    try:
        user = auth_service.verify_credentials(username, password)

    except Exception:
        logger.warning("AUTH_LOGIN_FAILED", extra={"username": username})

        # 🔴 CRITICAL: ALWAYS RETURN ON FAILURE
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid username or password",
                }
            },
        )

    # ✅ SUCCESS
    logger.info(
        "AUTH_LOGIN_SUCCESS",
        extra={"username": username, "userId": user["id"]},
    )

    # 🔐 MFA REQUIRED
    if user.get("totp_secret"):
        return {
            "mfaRequired": True,
            "username": username,
        }

    # 🔐 CREATE SESSION
    token = auth_service.create_session(user["id"])

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=False,  # ⚠️ set True in production
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )

    return {"success": True}


# ---------------------------------------------------------
# MFA VERIFY
# ---------------------------------------------------------
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

    # ✅ MFA SUCCESS → CREATE SESSION
    token = auth_service.create_session(user["id"])

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )

    logger.info(
        "AUTH_MFA_SUCCESS",
        extra={"username": username, "userId": user["id"]},
    )

    return {"success": True}


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------
@router.post("/logout")
async def logout(request: Request, user_id: int = Depends(require_auth)):
    token = request.cookies.get(settings.auth_cookie_name)

    logger.info("AUTH_LOGOUT", extra={"userId": user_id})

    auth_service.logout(token)

    response = JSONResponse(status_code=204, content={})
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
    )

    return response


# ---------------------------------------------------------
# CURRENT USER
# ---------------------------------------------------------
@router.get("/me")
async def me(user=Depends(require_auth)):
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
    }