"""Pydantic models for normalized transport transactions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TransportRequest(BaseModel):
    """Normalized transport request payload."""

    method: str = "UNKNOWN"
    url: str = ""
    headers: dict[str, Any] = Field(default_factory=dict)


class TransportResponse(BaseModel):
    """Normalized transport response payload."""

    status: int = 0
    duration_ms: int = 0


class TransportEvent(BaseModel):
    """Normalized transport event derived from an OpenHIM transaction."""

    model_config = ConfigDict(extra="ignore")

    transaction_id: str
    channel: str = "unknown"
    request: TransportRequest
    response: TransportResponse
    source_ip: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpenHIMRequestPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: str | None = None
    path: str | None = None
    url: str | None = None
    headers: dict[str, Any] | list[Any] | str | None = None
    host: str | None = None
    port: int | str | None = None
    timestamp: str | None = None


class OpenHIMResponsePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int | str | None = None
    statusCode: int | str | None = None
    duration: int | str | None = None
    duration_ms: int | str | None = None
    timestamp: str | None = None


class OpenHIMTransactionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    _id: str | None = None
    transactionID: str | None = None
    channelID: str | None = None
    channel: str | None = None
    clientIP: str | None = None
    request: OpenHIMRequestPayload
    response: OpenHIMResponsePayload
