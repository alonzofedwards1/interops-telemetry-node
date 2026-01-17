from fastapi import HTTPException, Request

from app.db.connection import get_connection
from app.config.settings import get_settings
from app.auth.service import hash_token

settings = get_settings()


def require_auth(request: Request) -> int:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    token_hash = hash_token(token)
    conn = get_connection()
    row = conn.execute(
        """
        SELECT user_id, expires_at
        FROM telemetry_sessions
        WHERE token_hash = ?
          AND expires_at > strftime('%s','now')
        """,
        (token_hash,),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    request.state.user_id = row["user_id"]
    return row["user_id"]
