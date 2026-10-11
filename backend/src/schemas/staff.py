"""Pydantic schemas for staff authentication and policy document management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StaffLoginRequest(BaseModel):
    """Staff authentication credentials for POST /api/auth/staff/login."""

    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


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
