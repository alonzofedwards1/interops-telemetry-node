import hmac
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.dependencies import require_auth
from app.auth.service import clear_session, hash_password, issue_session
from app.config.settings import get_settings
from app.db.connection import get_connection

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


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
        return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

    provided_hash = hash_password(payload.password)
    stored_hash = row["password_hash"]
    is_password_match = len(stored_hash) == len(provided_hash) and hmac.compare_digest(
        stored_hash, provided_hash
    )

    if not is_password_match:
        return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

    token, expires_at = issue_session(row["id"])
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
    )

    return {"username": payload.username, "expiresAt": expires_at}


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
    )
    return response


@router.get("/me")
async def me(user_id: int = Depends(require_auth)):
    return {"userId": user_id}
