from fastapi import APIRouter, Request
from app.transport.ingest_openhim import ingest_openhim_transactions

router = APIRouter()

@router.post("/transport/ingest-openhim")
async def ingest_openhim(request: Request):
    """
    Trigger transport-layer ingest from OpenHIM.
    Writes only to transport_events.
    """
    ingest_openhim_transactions()
    return {"status": "accepted", "source": "openhim"}