from fastapi import HTTPException, Request

from app.auth.service import validate_session
from app.config.settings import get_settings

settings = get_settings()


def require_auth(request: Request) -> int:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = validate_session(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    return user_id