"""Pydantic schemas for chat sessions, conversations, messages, and citation metadata."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RetrievalMetadataDTO(BaseModel):
    """Data transfer object for ChromaDB chunk citation audit trails."""

    model_config = ConfigDict(from_attributes=True)

    retrieval_id: str
    message_id: str
    chunk_id: str
    document_source: str
    similarity_score: Optional[float] = None
    chunk_text: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class MessageCreate(BaseModel):
    """Payload for submitting a new message."""

    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str = Field(..., min_length=1, description="Text body of the message")


class MessageDTO(BaseModel):
    """Full representation of a message turn."""

    model_config = ConfigDict(from_attributes=True)

    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    retrieval_metadata: List[RetrievalMetadataDTO] = Field(default_factory=list)


class ConversationCreate(BaseModel):
    """Payload for initiating a conversation thread."""

    session_id: str
    system_variant: str = Field("RAG", description="'RAG' or 'BASELINE'")


class ConversationDTO(BaseModel):
    """Full representation of a multi-turn conversation."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    session_id: str
    system_variant: str
    created_at: datetime
    messages: List[MessageDTO] = Field(default_factory=list)


class SessionCreate(BaseModel):
    """Payload for initiating a passenger session."""

    passenger_id: Optional[str] = None


class SessionDTO(BaseModel):
    """Full representation of an active session."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    passenger_id: Optional[str] = None
    created_at: datetime
    last_active: datetime


class ChatQueryRequest(BaseModel):
    """API payload for passenger queries sent to POST /api/chat."""

    session_id: Optional[str] = Field(None, description="Existing session ID; created if omitted")
    conversation_id: Optional[str] = Field(None, description="Existing conversation thread ID")
    message: str = Field(..., min_length=1, description="Customer question")
    system_variant: str = Field("RAG", description="Switch between RAG pipeline and Baseline control")


class ChatQueryResponse(BaseModel):
    """Structured response returned by the RAG backend."""

    session_id: str
    conversation_id: str
    message_id: str
    response: str
    system_variant: str
    citations: List[RetrievalMetadataDTO] = Field(default_factory=list)
