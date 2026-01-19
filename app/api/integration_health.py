import logging
import sqlite3
from fastapi import APIRouter, Depends, HTTPException

from app.integration_health.store import get_integration_health
from app.db.connection import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["Integration Health"]
)

@router.get("/integrations")
def integration_health(conn: sqlite3.Connection = Depends(get_connection)):
    try:
        return get_integration_health(conn)
    except Exception:
        logger.exception("Failed to load integration health")
        raise HTTPException(status_code=500, detail="Internal server error")
