import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.dependencies import require_auth
from app.auth.service import clear_session, issue_session
from app.config.settings import get_settings
from app.db.connection import get_connection
from app.security.passwords import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()
logger = logging.getLogger(__name__)


# =========================================================
# Models
# =========================================================

class LoginRequest(BaseModel):
    username: str
    password: str


# =========================================================
# Login
# =========================================================

@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    conn = get_connection()

    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = %s",
            (payload.username,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        logger.warning(
            "AUTH_LOGIN_FAILED_UNKNOWN_USER",
            extra={"username": payload.username},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored_hash = row["password_hash"]

    try:
        if not verify_password(payload.password, stored_hash):
            logger.warning(
                "AUTH_LOGIN_FAILED_BAD_PASSWORD",
                extra={"username": payload.username, "userId": row["id"]},
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")

    except ValueError:
        logger.warning(
            "AUTH_LOGIN_FAILED_INVALID_HASH",
            extra={"username": payload.username, "userId": row["id"]},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # -----------------------------------------------------
    # Create session
    # -----------------------------------------------------

    token, _ = issue_session(row["id"])

    # -----------------------------------------------------
    # Set session cookie
    # -----------------------------------------------------

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=False,  # must be False for localhost
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )

    logger.info(
        "AUTH_LOGIN_SUCCESS",
        extra={
            "username": payload.username,
            "userId": row["id"]
        }
    )

    return {"success": True}


# =========================================================
# Logout
# =========================================================

@router.post("/logout")
async def logout(request: Request, user_id: int = Depends(require_auth)):
    token = request.cookies.get(settings.auth_cookie_name)

    if token:
        clear_session(token)

    response = JSONResponse(status_code=204, content={})

    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )

    return response


# =========================================================
# Session Check
# =========================================================

@router.get("/me")
async def me(user_id: int = Depends(require_auth)):
    return {"userId": user_id}
