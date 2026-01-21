from pydantic import BaseModel, ConfigDict, Field


class FindingOut(BaseModel):
    id: str = Field(..., description="Finding identifier")
    executionId: str | None = Field(None, description="Related execution identifier")
    executionType: str | None = Field(None, description="Execution type")
    severity: str = Field(..., description="Finding severity")
    category: str = Field(..., description="Finding category")
    summary: str = Field(..., description="Finding summary")
    technicalDetail: str | None = Field(None, description="Technical details")
    recommendedAction: str | None = Field(None, description="Recommended action")
    status: str = Field(..., description="Finding status")
    relatedOid: str | None = Field(None, description="Related OID")
    organization: str | None = Field(None, description="Related organization name")
    firstSeenAt: str | None = Field(None, description="First seen timestamp")
    lastSeenAt: str | None = Field(None, description="Last seen timestamp")
    createdAt: str | None = Field(None, description="Created timestamp")
    updatedAt: str | None = Field(None, description="Updated timestamp")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class FindingCreate(BaseModel):
    id: str = Field(..., description="Finding identifier")
    executionId: str | None = Field(None, description="Related execution identifier")
    executionType: str = Field("PD", description="Execution type")
    severity: str = Field(..., description="Finding severity")
    category: str = Field(..., description="Finding category")
    summary: str = Field(..., description="Finding summary")
    technicalDetail: str | None = Field(None, description="Technical details")
    recommendedAction: str | None = Field(None, description="Recommended action")
    status: str = Field("open", description="Finding status")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class FindingStatusUpdate(BaseModel):
    status: str = Field(..., description="Updated finding status")

    model_config = ConfigDict(populate_by_name=True)


class FindingsCountOut(BaseModel):
    total: int = Field(..., ge=0)
    warnings: int = Field(..., ge=0)
    critical: int = Field(..., ge=0)
    info: int = Field(..., ge=0)
    open: int = Field(..., ge=0)
    acknowledged: int = Field(..., ge=0)
    resolved: int = Field(..., ge=0)

    model_config = ConfigDict(populate_by_name=True)
