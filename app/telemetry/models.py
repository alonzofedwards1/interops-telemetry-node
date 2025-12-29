from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceInfo(BaseModel):
    system: Optional[str] = Field(None, description="Originating system identifier")
    channelId: Optional[str] = Field(None, description="Mirth channel identifier")
    environment: Optional[str] = Field(None, description="Deployment environment")

    model_config = ConfigDict(extra="allow")


class CorrelationInfo(BaseModel):
    requestId: Optional[str] = Field(None, description="Client request identifier")
    messageId: Optional[str] = Field(None, description="Message identifier")

    model_config = ConfigDict(extra="allow")


class ExecutionInfo(BaseModel):
    durationMs: Optional[int] = Field(None, ge=0, description="Execution duration in milliseconds")

    model_config = ConfigDict(extra="allow")


class OutcomeInfo(BaseModel):
    status: Optional[Literal["SUCCESS", "FAILURE"]] = Field(None, description="Execution status")
    resultCount: Optional[int] = Field(None, ge=0, description="Count of results returned")

    model_config = ConfigDict(extra="allow")


class ProtocolInfo(BaseModel):
    standard: Optional[str] = Field(None, description="Protocol standard (e.g., HL7v3)")
    interactionId: Optional[str] = Field(None, description="Interaction identifier")

    model_config = ConfigDict(extra="allow")


class TelemetryEvent(BaseModel):
    eventId: str = Field(..., description="Unique event identifier")
    eventType: str = Field(..., description="Type of telemetry event")
    timestamp: datetime = Field(..., description="Event timestamp (ISO 8601)")

    source: Optional[SourceInfo] = Field(None, description="Event source metadata")
    correlation: Optional[CorrelationInfo] = Field(None, description="Correlation identifiers")
    execution: Optional[ExecutionInfo] = Field(None, description="Execution metrics")
    outcome: Optional[OutcomeInfo] = Field(None, description="Outcome summary")
    protocol: Optional[ProtocolInfo] = Field(None, description="Protocol metadata")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="allow",
        populate_by_name=True,
    )
