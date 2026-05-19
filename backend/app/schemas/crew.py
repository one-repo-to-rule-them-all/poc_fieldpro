"""Crew and CrewMember Pydantic v2 schemas."""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Crew base
# --------------------------------------------------------------------------- #

class CrewBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    lead_id: uuid.UUID | None = None


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #

class CrewCreate(CrewBase):
    pass


# --------------------------------------------------------------------------- #
# Update  (PATCH semantics — all fields optional)
# --------------------------------------------------------------------------- #

class CrewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    lead_id: uuid.UUID | None = None
    is_active: bool | None = None


# --------------------------------------------------------------------------- #
# Crew member schemas
# --------------------------------------------------------------------------- #

class CrewMemberAdd(BaseModel):
    user_id: uuid.UUID


class CrewMemberRemove(BaseModel):
    user_id: uuid.UUID


class CrewMemberResponse(BaseModel):
    user_id: uuid.UUID
    crew_id: uuid.UUID
    joined_at: datetime
    left_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Response
# --------------------------------------------------------------------------- #

class CrewResponse(CrewBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    members: list[CrewMemberResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CrewListResponse(BaseModel):
    """Slim representation used in paginated list views."""

    id: uuid.UUID
    name: str
    code: str
    description: str | None = None
    is_active: bool
    member_count: int = 0
    lead_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CrewMemberUserSummary(BaseModel):
    """Lightweight user info embedded in crew member responses."""

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class CrewMemberDetail(BaseModel):
    """Full crew member record as returned by the API."""

    id: uuid.UUID
    crew_id: uuid.UUID
    user_id: uuid.UUID
    user: CrewMemberUserSummary | None = None
    role: str
    joined_at: datetime
    left_at: datetime | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CrewDetailResponse(BaseModel):
    """Full crew representation returned by get/create/update endpoints."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    code: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    members: list[CrewMemberDetail] = []

    model_config = ConfigDict(from_attributes=True)
