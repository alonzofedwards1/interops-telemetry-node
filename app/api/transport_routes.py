from fastapi import APIRouter, Request

from app.transport.ingest_openhim import ingest_openhim_transactions

router = APIRouter()


@router.post("/transport/ingest-openhim")
async def ingest_openhim(request: Request):
    """
    Transport-layer ingest endpoint.
    Called by OpenHIM.
    Writes only to transport_events.
    """
    payload = await request.json()
    headers = dict(request.headers)

    ingest_openhim_transactions(payload=payload, headers=headers)

    return {"status": "accepted", "source": "openhim"}