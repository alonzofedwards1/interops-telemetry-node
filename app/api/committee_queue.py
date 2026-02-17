import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/committee-queue", tags=["committee-queue"])


@router.get("")
async def get_committee_queue() -> list[dict]:
    """Return a placeholder committee queue to satisfy frontend polling."""

    logger.debug("committee queue requested")
    return []
