import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_auth
from app.auth.models import LoginRequest, LoginResponse
from app.auth import service as auth_service
from app.config.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response):
    logger.info("AUTH_LOGIN_ATTEMPT", extra={"username": payload.username})

    try:
        token = auth_service.login(payload.username, payload.password)
    except Exception:
        logger.warning(
            "AUTH_LOGIN_FAILED",
            extra={"username": payload.username},
        )
        raise

    logger.info("AUTH_LOGIN_SUCCESS", extra={"username": payload.username})

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

    logger.info("AUTH_LOGOUT", extra={"userId": user_id})

    auth_service.logout(token)

    response = JSONResponse(status_code=204, content={})
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
    )

    return response

@router.get("/me")
async def me(user=Depends(require_auth)):
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
    }