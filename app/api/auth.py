import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_auth
from app.auth.models import LoginRequest, LoginResponse
from app.auth.service import clear_session, issue_session
from app.config.settings import get_settings
from app.db.connection import get_connection
from app.security.passwords import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response):
    conn = get_connection()

    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = %s",
            (payload.username,),
        ).fetchone()
    finally:
        conn.close()

    if not user:
        logger.warning("AUTH_LOGIN_FAILED_UNKNOWN_USER", extra={"username": payload.username})
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user["password_hash"]):
        logger.warning(
            "AUTH_LOGIN_FAILED_BAD_PASSWORD",
            extra={"username": payload.username, "userId": user["id"]},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = issue_session(user["id"])

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )

    return {"success": True}


@router.post("/logout")
async def logout(request: Request, user_id: int = Depends(require_auth)):
    token = request.cookies.get(settings.auth_cookie_name)

    if token:
        clear_session(token)

    response = JSONResponse(status_code=204, content={})
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
    )

    return response


@router.get("/me")
async def me(user_id: int = Depends(require_auth)):
    return {"userId": user_id}
