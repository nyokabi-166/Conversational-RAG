"""SQLAlchemy ORM entity models implementing Table 4.1 from Capstone documentation."""

import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import relationship

from src.core.database import Base


def generate_uuid() -> str:
    """Generate a standard 36-character UUID string."""
    return str(uuid.uuid4())


class PassengerAccount(Base):
    """Registered passenger account with credentials and role."""

    __tablename__ = "passenger_accounts"

    passenger_id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="passenger")  # 'passenger'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("Session", back_populates="passenger")
    saved_trips = relationship(
        "SavedTrip", back_populates="passenger", cascade="all, delete-orphan"
    )


class Session(Base):
    """Anchors customer interaction sessions for multi-turn context."""

    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=generate_uuid)
    passenger_id = Column(
        String(36),
        ForeignKey("passenger_accounts.passenger_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    passenger = relationship("PassengerAccount", back_populates="sessions")
    conversations = relationship(
        "Conversation",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class Conversation(Base):
    """Multi-turn conversation thread, logging RAG vs Baseline experimental variants."""

    __tablename__ = "conversations"

    conversation_id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    system_variant = Column(String(20), default="RAG")  # 'RAG' vs 'BASELINE'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    evaluation_scores = relationship(
        "EvaluationScore",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    """Individual dialog turns (user, assistant, system) with exact timestamps."""

    __tablename__ = "messages"

    message_id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
    retrieval_metadata = relationship(
        "RetrievalMetadata",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class RetrievalMetadata(Base):
    """Audit log of retrieved ChromaDB vector chunks cited for an assistant response."""

    __tablename__ = "retrieval_metadata"

    retrieval_id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(
        String(36),
        ForeignKey("messages.message_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id = Column(String(100), nullable=False)
    document_source = Column(String(255), nullable=False)
    similarity_score = Column(Float, nullable=True)
    chunk_text = Column(Text, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), server_default=func.now())

    message = relationship("Message", back_populates="retrieval_metadata")


class EvaluationScore(Base):
    """Quantitative RAGAS benchmark scores (Faithfulness, Relevancy, Recall) scored by LLM Judge."""

    __tablename__ = "evaluation_scores"

    evaluation_id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    system_variant = Column(String(20), nullable=False)  # 'RAG' vs 'BASELINE'
    pillar = Column(
        String(50), nullable=False, index=True
    )  # 'Baggage', 'Rebooking', etc.
    faithfulness_score = Column(Float, nullable=True)
    answer_relevancy_score = Column(Float, nullable=True)
    context_recall_score = Column(Float, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="evaluation_scores")


class StaffAccount(Base):
    """Airline administrator / support staff account with password hashing for document uploads."""

    __tablename__ = "staff_accounts"
    __table_args__ = (
        Index(
            "uq_staff_accounts_single_super_admin",
            "role",
            unique=True,
            postgresql_where=text("role = 'super_admin'"),
            sqlite_where=text("role = 'super_admin'"),
        ),
    )

    staff_id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="policy_admin")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document_uploads = relationship("DocumentUpload", back_populates="staff")


class DocumentUpload(Base):
    """Audit log of policy documents uploaded and indexed into the ChromaDB vector database."""

    __tablename__ = "document_uploads"

    upload_id = Column(String(36), primary_key=True, default=generate_uuid)
    staff_id = Column(
        String(36),
        ForeignKey("staff_accounts.staff_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=True)
    chunk_count = Column(Integer, default=0)
    status = Column(String(50), default="INDEXED")  # 'UPLOADING', 'INDEXED', 'FAILED'
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    staff = relationship("StaffAccount", back_populates="document_uploads")


class SavedTrip(Base):
    """Passenger-owned trip details; intentionally excludes booking credentials."""

    __tablename__ = "saved_trips"

    trip_id = Column(String(36), primary_key=True, default=generate_uuid)
    passenger_id = Column(
        String(36),
        ForeignKey("passenger_accounts.passenger_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    departure_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)
    flight_number = Column(String(12), nullable=True)
    label = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reminders = relationship(
        "TripReminder", back_populates="trip", cascade="all, delete-orphan"
    )
    passenger = relationship("PassengerAccount", back_populates="saved_trips")


class TripReminder(Base):
    """A passenger-created, in-app reminder for a saved trip."""

    __tablename__ = "trip_reminders"

    reminder_id = Column(String(36), primary_key=True, default=generate_uuid)
    trip_id = Column(
        String(36),
        ForeignKey("saved_trips.trip_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(160), nullable=False)
    remind_at = Column(DateTime(timezone=True), nullable=False)
    completed = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("SavedTrip", back_populates="reminders")
