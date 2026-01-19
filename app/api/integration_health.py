import logging

from fastapi import APIRouter, Depends, HTTPException

from app.db.connection import get_connection
from app.integration_health.store import get_integration_health

router = APIRouter(prefix="/health", tags=["integration-health"])
logger = logging.getLogger(__name__)


@router.get("/integrations")
async def integration_health(conn=Depends(get_connection)):
    try:
        return get_integration_health(conn)
    except Exception:
        logger.exception("Failed to load integration health")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        try:
            conn.close()
        except Exception:
            logger.exception("Failed to close integration health connection")
