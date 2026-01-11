from pydantic import BaseModel, ConfigDict, Field


class PDExecution(BaseModel):
    requestId: str = Field(..., description="PD request identifier")
    startedAt: str = Field(..., description="Execution start timestamp (ISO 8601)")
    completedAt: str = Field(..., description="Execution completion timestamp (ISO 8601)")
    executionTimeMs: int = Field(..., ge=0, description="Execution duration in milliseconds")
    outcome: str = Field(..., description="Execution outcome")
    channelId: str | None = Field(None, description="Source channel identifier")
    environment: str | None = Field(None, description="Source environment")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )


class PDExecutionCount(BaseModel):
    count: int = Field(..., ge=0, description="Total PD execution count")

    model_config = ConfigDict(populate_by_name=True)
