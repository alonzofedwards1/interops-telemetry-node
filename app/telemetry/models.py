from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceInfo(BaseModel):
    channelId: Optional[str] = Field(None, description="Mirth channel identifier")
    environment: Optional[str] = Field(None, description="Deployment environment")

    model_config = ConfigDict(extra="allow")


class CorrelationInfo(BaseModel):
    requestId: Optional[str] = Field(None, description="Client request identifier")

    model_config = ConfigDict(extra="allow")


class OutcomeInfo(BaseModel):
    status: Optional[str] = Field(None, description="Execution status")
    durationMs: Optional[int] = Field(None, ge=0, description="Execution duration in milliseconds")

    model_config = ConfigDict(extra="allow")


class TelemetryEvent(BaseModel):
    eventId: str = Field(..., description="Unique event identifier")
    eventType: str = Field(..., description="Type of telemetry event")
    timestamp: str = Field(..., description="Event timestamp (ISO 8601 UTC)")

    source: Optional[SourceInfo] = Field(None, description="Event source metadata")
    correlation: Optional[CorrelationInfo] = Field(None, description="Correlation identifiers")
    outcome: Optional[OutcomeInfo] = Field(None, description="Outcome summary")
    sourceOid: Optional[str] = Field(None, description="Source OID observed")
    targetOid: Optional[str] = Field(None, description="Target OID observed")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="allow",
        populate_by_name=True,
    )
