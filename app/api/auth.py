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


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (payload.username,),
    ).fetchone()
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

    token, _ = issue_session(row["id"])

    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )

    logger.info("AUTH_LOGIN_SUCCESS", extra={"username": payload.username, "userId": row["id"]})
    return {"success": True}


@router.post("/logout")
async def logout(request: Request, user_id: int = Depends(require_auth)):
    token = request.cookies.get(settings.auth_cookie_name)
    clear_session(token)

    response = JSONResponse(status_code=204, content={})
    response.delete_cookie(
        settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/me")
async def me(user_id: int = Depends(require_auth)):
    return {"userId": user_id}
