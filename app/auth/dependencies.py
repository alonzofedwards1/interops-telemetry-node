from fastapi import HTTPException, Request

from app.auth.service import validate_session
from app.auth import repository
from app.config.settings import get_settings

settings = get_settings()


def require_auth(request: Request):
    token = request.cookies.get(settings.auth_cookie_name)

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = validate_session(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = repository.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return user