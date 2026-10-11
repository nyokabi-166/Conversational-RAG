"""Pydantic schemas for user authentication, registration, profiles, and chat history."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from src.schemas.chat import MessageDTO


class RegisterRequest(BaseModel):
    """Passenger account registration."""

    email: str = Field(..., min_length=5, description="Passenger email address")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    """Universal login request for both passengers (via email) and staff (via username)."""

    username_or_email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=4)


class TokenResponse(BaseModel):
    """JWT response payload."""

    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str  # 'passenger', 'policy_admin', 'super_admin'
    identifier: str  # email or username
    full_name: Optional[str] = None


class UserProfile(BaseModel):
    """Current authenticated user profile."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    identifier: str
    role: str
    full_name: Optional[str] = None
    created_at: Optional[datetime] = None


class ConversationHistorySummary(BaseModel):
    """Summary of a past conversation thread for passenger history drawer."""

    conversation_id: str
    session_id: str
    created_at: datetime
    system_variant: str
    message_count: int
    last_message: Optional[str] = None


class ConversationHistoryDetail(BaseModel):
    """Detailed conversation thread with all dialog turns and citations."""

    conversation_id: str
    session_id: str
    created_at: datetime
    system_variant: str
    messages: List[MessageDTO] = Field(default_factory=list)
