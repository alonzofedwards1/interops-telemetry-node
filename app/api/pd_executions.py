import logging
from typing import List

from fastapi import APIRouter, HTTPException

from app.pd.models import PDExecution, PDExecutionCount
from app.pd.service import (
    fetch_execution_telemetry,
    fetch_pd_execution_count,
    fetch_pd_executions,
)

router = APIRouter(prefix="/pd-executions", tags=["pd-executions"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[PDExecution])
async def get_pd_executions():
    try:
        return fetch_pd_executions()
    except Exception:
        logger.exception("Failed to load PD executions")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/count", response_model=PDExecutionCount)
async def get_pd_execution_count():
    try:
        return fetch_pd_execution_count()
    except Exception:
        logger.exception("Failed to count PD executions")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{request_id}/telemetry")
async def get_execution_telemetry(request_id: str):
    try:
        return fetch_execution_telemetry(request_id)

    except Exception:
        logger.exception("Failed to load PD execution telemetry")
        raise HTTPException(status_code=500, detail="Internal server error")
