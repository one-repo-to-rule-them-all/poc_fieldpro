"""Location Pydantic v2 schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------- #
# Nested address schema
# --------------------------------------------------------------------------- #

class AddressSchema(BaseModel):
    street: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    zip: str = Field(..., min_length=1)
    country: str = "US"


# --------------------------------------------------------------------------- #
# Base
# --------------------------------------------------------------------------- #

ServiceDay = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    client_id: uuid.UUID
    address: AddressSchema
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    geofence_radius_m: int = Field(default=100, ge=10, le=5000)
    access_instructions: str | None = None
    special_requirements: str | None = None
    service_days: list[ServiceDay] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lat_lon_both_or_neither(self) -> LocationBase:
        lat_set = self.latitude is not None
        lon_set = self.longitude is not None
        if lat_set != lon_set:
            raise ValueError("latitude and longitude must both be set or both be omitted")
        return self


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #

class LocationCreate(LocationBase):
    pass


# --------------------------------------------------------------------------- #
# Update  (PATCH semantics — all fields optional)
# --------------------------------------------------------------------------- #

class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: AddressSchema | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    geofence_radius_m: int | None = Field(default=None, ge=10, le=5000)
    access_instructions: str | None = None
    special_requirements: str | None = None
    service_days: list[ServiceDay] | None = None
    is_active: bool | None = None


# --------------------------------------------------------------------------- #
# Response
# --------------------------------------------------------------------------- #

class LocationResponse(LocationBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LocationListResponse(BaseModel):
    """Slim representation used in paginated list views."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    name: str
    address: dict | None = None
    latitude: str | None = None
    longitude: str | None = None
    geofence_radius_meters: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocationDetailResponse(BaseModel):
    """Full location representation returned by get/create/update endpoints."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    name: str
    address: dict | None = None
    latitude: str | None = None
    longitude: str | None = None
    geofence_radius_meters: int
    access_instructions: str | None = None
    special_requirements: str | None = None
    is_active: bool
    qr_code_token: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
