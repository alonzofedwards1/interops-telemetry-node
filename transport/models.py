from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TransportRequest(BaseModel):

    method: str = "UNKNOWN"
    url: str = ""
    headers: dict[str, Any] = Field(default_factory=dict)


class TransportResponse(BaseModel):

    status: int = 0
    duration_ms: int = 0


class TransportEvent(BaseModel):

    model_config = ConfigDict(extra="ignore")

    transaction_id: str
    channel: str = "unknown"
    request: TransportRequest
    response: TransportResponse
    source_ip: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
