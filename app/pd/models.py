from pydantic import BaseModel, ConfigDict, Field


class PDExecution(BaseModel):
    requestId: str = Field(..., description="PD request identifier")
    startedAt: str = Field(..., description="Execution start timestamp (ISO 8601)")
    completedAt: str = Field(..., description="Execution completion timestamp (ISO 8601)")
    executionTimeMs: int = Field(..., ge=0, description="Execution duration in milliseconds")
    outcome: str = Field(..., description="Execution outcome")
    channelId: str | None = Field(None, description="Source channel identifier")
    environment: str | None = Field(None, description="Source environment")
    sourceOid: str | None = Field(None, description="Source organization OID")
    sourceOrganizationName: str | None = Field(
        None, description="Resolved source organization name"
    )
    certStatus: str = Field(..., description="Certificate validation status")
    certThumbprint: str | None = Field(None, description="Certificate thumbprint")
    failureStage: str | None = Field(None, description="Failure stage classification")
    rootCause: str | None = Field(None, description="Root cause classification")
    httpStatus: int | None = Field(None, description="HTTP status code")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )


class PDExecutionCount(BaseModel):
    count: int = Field(..., ge=0, description="Total PD execution count")

    model_config = ConfigDict(populate_by_name=True)
