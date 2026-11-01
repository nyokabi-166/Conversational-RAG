"""Pydantic schemas for staff authentication and policy document management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StaffLoginRequest(BaseModel):
    """Staff authentication credentials for POST /auth/staff/login."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class AdminBootstrapRequest(BaseModel):
    """One-time first-admin setup credentials."""

    setup_token: str = Field(..., min_length=32, max_length=512)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=12, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Use letters, numbers, hyphens, or underscores only.")
        return normalized


class StaffCreateRequest(BaseModel):
    """Create a policy staff account from the authenticated admin workspace."""

    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=12, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Use letters, numbers, hyphens, or underscores only.")
        return normalized


class StaffPasswordResetRequest(BaseModel):
    """Set a new password for an existing policy staff account."""

    password: str = Field(..., min_length=12, max_length=128)


class AdminSetupStatus(BaseModel):
    setup_required: bool
    setup_enabled: bool


class StaffTokenResponse(BaseModel):
    """JWT bearer token response."""

    access_token: str
    token_type: str = "bearer"
    staff_id: str
    username: str
    role: str


class StaffDTO(BaseModel):
    """Representation of an airline staff account."""

    model_config = ConfigDict(from_attributes=True)

    staff_id: str
    username: str
    full_name: Optional[str] = None
    role: str
    created_at: datetime


class DocumentUploadDTO(BaseModel):
    """Representation of an uploaded policy PDF document."""

    model_config = ConfigDict(from_attributes=True)

    upload_id: str
    staff_id: Optional[str] = None
    filename: str
    file_size_bytes: Optional[int] = None
    chunk_count: int
    status: str
    uploaded_at: datetime
