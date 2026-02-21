from fastapi import APIRouter

from app.transport.ingest_openhim import ingest_openhim_transactions

router = APIRouter()


@router.post("/api/transport/ingest-openhim")
async def ingest_openhim() -> dict[str, str]:
    """
    Transport-layer ingest endpoint.
    Called by OpenHIM.
    Writes only to transport_events.
    """
    ingest_openhim_transactions()
    return {"status": "accepted", "source": "openhim"}
