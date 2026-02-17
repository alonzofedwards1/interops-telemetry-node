"""Pydantic models for normalized transport events."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TransportRequest(BaseModel):
    """Normalized request details from an OpenHIM transaction."""

    method: str = Field(..., description="HTTP method for the request")
    url: str = Field(..., description="Request URL")
    headers: dict[str, Any] = Field(default_factory=dict, description="Request headers")

    model_config = ConfigDict(extra="ignore")


class TransportResponse(BaseModel):
    """Normalized response details from an OpenHIM transaction."""

    status: int = Field(..., description="HTTP response status code")
    duration_ms: int = Field(..., ge=0, description="Round-trip duration in milliseconds")

    model_config = ConfigDict(extra="ignore")


class TransportEvent(BaseModel):
    """Normalized transport-level telemetry event."""

    transaction_id: str = Field(..., description="OpenHIM transaction identifier")
    channel: str = Field(..., description="OpenHIM channel identifier or name")
    request: TransportRequest
    response: TransportResponse
    source_ip: str | None = Field(default=None, description="Client/source IP address")
    timestamp: datetime = Field(..., description="Transaction timestamp")

    model_config = ConfigDict(extra="ignore")
