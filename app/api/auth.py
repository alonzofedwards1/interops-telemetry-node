import hmac
import hashlib
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.dependencies import require_auth
from app.auth.service import clear_session, issue_session
from app.config.settings import get_settings
from app.db.connection import get_connection

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class LoginRequest(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    raw = f"{settings.auth_password_salt}:{password}"
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (payload.username,),
    ).fetchone()
    conn.close()

    if not row:
        print("USER NOT FOUND:", payload.username)
        return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

    provided_hash = hash_password(payload.password)
    stored_hash = row["password_hash"]

    # 🔴 DEBUG OUTPUT
    print("AUTH SALT IN USE:", settings.auth_password_salt)
    print("PASSWORD RECEIVED:", payload.password)
    print("COMPUTED HASH:", provided_hash)
    print("DB HASH:", stored_hash)

    is_password_match = (
        len(stored_hash) == len(provided_hash)
        and hmac.compare_digest(stored_hash, provided_hash)
    )

    print("PASSWORD MATCH:", is_password_match)

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
