"""Request and response schemas for authentication and conversation history."""

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.schemas.chat import MessageDTO


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("A valid email address is required.")
        return normalized


class LoginRequest(BaseModel):
    username_or_email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    identifier: str
    full_name: Optional[str] = None


class UserProfile(BaseModel):
    user_id: str
    identifier: str
    role: str
    full_name: Optional[str] = None


class ConversationHistorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    session_id: str
    created_at: datetime
    system_variant: str
    message_count: int
    last_message: Optional[str] = None


class ConversationHistoryDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    session_id: str
    created_at: datetime
    system_variant: str
    messages: List[MessageDTO] = Field(default_factory=list)
