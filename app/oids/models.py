from pydantic import BaseModel, ConfigDict, Field


class OidListItem(BaseModel):
    oid: str = Field(..., description="OID value")
    displayName: str | None = Field(None, description="Display name")
    ownerOrg: str | None = Field(None, description="Owning organization")
    status: str = Field(..., description="OID status")
    confidence: str = Field(..., description="Confidence level")
    firstSeen: str | None = Field(None, description="First seen timestamp")
    lastSeen: str | None = Field(None, description="Last seen timestamp")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class OidUsage(BaseModel):
    pd: int = Field(..., ge=0)
    qd: int = Field(..., ge=0)
    rd: int = Field(..., ge=0)
    xds: int = Field(..., ge=0)

    model_config = ConfigDict(populate_by_name=True)


class OidDetail(BaseModel):
    oid: str = Field(..., description="OID value")
    displayName: str | None = Field(None, description="Display name")
    ownerOrg: str | None = Field(None, description="Owning organization")
    status: str = Field(..., description="OID status")
    confidence: str = Field(..., description="Confidence level")
    firstSeen: str | None = Field(None, description="First seen timestamp")
    lastSeen: str | None = Field(None, description="Last seen timestamp")
    usage: OidUsage

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class OidGovernanceRequest(BaseModel):
    action: str = Field(..., description="Governance action")
    notes: str | None = Field(None, description="Review notes")
    ownerOrg: str | None = Field(None, description="Owning organization")

    model_config = ConfigDict(populate_by_name=True)
