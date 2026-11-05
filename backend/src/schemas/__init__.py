"""Schemas package exporting all Pydantic DTOs."""

from src.schemas.auth import (
    ConversationHistoryDetail,
    ConversationHistorySummary,
    PassengerLoginRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)
from src.schemas.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    ConversationCreate,
    ConversationDTO,
    MessageCreate,
    MessageDTO,
    RetrievalMetadataDTO,
    SessionCreate,
    SessionDTO,
)
from src.schemas.evaluation import (
    EvaluationScoreCreate,
    EvaluationScoreDTO,
    PillarBenchmarkSummary,
)
from src.schemas.staff import (
    DocumentUploadDTO,
    StaffDTO,
    StaffLoginRequest,
    StaffTokenResponse,
)

__all__ = [
    "RetrievalMetadataDTO",
    "MessageCreate",
    "MessageDTO",
    "ConversationCreate",
    "ConversationDTO",
    "SessionCreate",
    "SessionDTO",
    "ChatQueryRequest",
    "ChatQueryResponse",
    "StaffLoginRequest",
    "StaffTokenResponse",
    "StaffDTO",
    "DocumentUploadDTO",
    "EvaluationScoreCreate",
    "EvaluationScoreDTO",
    "PillarBenchmarkSummary",
    "RegisterRequest",
    "PassengerLoginRequest",
    "TokenResponse",
    "UserProfile",
    "ConversationHistorySummary",
    "ConversationHistoryDetail",
]
