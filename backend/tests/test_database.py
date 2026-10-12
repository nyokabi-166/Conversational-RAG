"""Unit tests for SQLAlchemy database models and relationships."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base
from src.models.entities import (
    Conversation,
    DocumentUpload,
    EvaluationScore,
    Message,
    PassengerAccount,
    RetrievalMetadata,
    Session,
    StaffAccount,
)
from src.schemas.chat import (
    ConversationDTO,
    MessageDTO,
    RetrievalMetadataDTO,
    SessionDTO,
)
from src.schemas.evaluation import EvaluationScoreDTO
from src.schemas.staff import DocumentUploadDTO, StaffDTO


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session for unit testing."""
    test_engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def test_create_tables_and_passenger(db_session):
    """Verify PassengerAccount creation and session association."""
    passenger = PassengerAccount(email="jane.doe@example.com", full_name="Jane Doe")
    db_session.add(passenger)
    db_session.commit()
    db_session.refresh(passenger)

    assert passenger.passenger_id is not None
    assert passenger.email == "jane.doe@example.com"


def test_full_conversation_and_retrieval_flow(db_session):
    """Verify Session -> Conversation -> Message -> RetrievalMetadata lifecycle."""
    # 1. Create Session
    session = Session()
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # 2. Create Conversation
    conversation = Conversation(session_id=session.session_id, system_variant="RAG")
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    # 3. Create User & Assistant Messages
    msg_user = Message(
        conversation_id=conversation.conversation_id,
        role="user",
        content="What is the baggage limit for economy flights?",
    )
    msg_assistant = Message(
        conversation_id=conversation.conversation_id,
        role="assistant",
        content="Economy passengers are permitted 2 checked bags up to 23kg each.",
    )
    db_session.add_all([msg_user, msg_assistant])
    db_session.commit()
    db_session.refresh(msg_assistant)

    # 4. Create Retrieval Metadata Citation
    citation = RetrievalMetadata(
        message_id=msg_assistant.message_id,
        chunk_id="baggage_policy.pdf_chunk_12",
        document_source="Kenya_Airways_Baggage_Policy_2026.pdf",
        similarity_score=0.89,
        chunk_text="Economy Class Allowance: 2 pieces x 23 kg each.",
    )
    db_session.add(citation)
    db_session.commit()
    db_session.refresh(citation)

    # Verify relationships
    assert len(conversation.messages) == 2
    assert len(msg_assistant.retrieval_metadata) == 1
    assert (
        msg_assistant.retrieval_metadata[0].document_source
        == "Kenya_Airways_Baggage_Policy_2026.pdf"
    )

    # Verify Pydantic DTO serialization
    session_dto = SessionDTO.model_validate(session)
    assert session_dto.session_id == session.session_id

    citation_dto = RetrievalMetadataDTO.model_validate(citation)
    assert citation_dto.chunk_id == "baggage_policy.pdf_chunk_12"


def test_cascade_delete_session(db_session):
    """Verify that deleting a Session cascades to all conversations, messages, and citations."""
    session = Session()
    db_session.add(session)
    db_session.commit()

    conversation = Conversation(session_id=session.session_id)
    db_session.add(conversation)
    db_session.commit()

    message = Message(
        conversation_id=conversation.conversation_id, role="user", content="Test"
    )
    db_session.add(message)
    db_session.commit()

    citation = RetrievalMetadata(
        message_id=message.message_id,
        chunk_id="chunk_1",
        document_source="doc.pdf",
    )
    db_session.add(citation)
    db_session.commit()

    # Delete session
    db_session.delete(session)
    db_session.commit()

    assert db_session.query(Session).count() == 0
    assert db_session.query(Conversation).count() == 0
    assert db_session.query(Message).count() == 0
    assert db_session.query(RetrievalMetadata).count() == 0


def test_staff_and_document_upload(db_session):
    """Verify staff account creation and document upload tracking."""
    staff = StaffAccount(
        username="admin_sarah",
        password_hash="$2b$12$e8Y7z7D...fakehash",
        full_name="Sarah Staff",
        role="policy_admin",
    )
    db_session.add(staff)
    db_session.commit()
    db_session.refresh(staff)

    upload = DocumentUpload(
        staff_id=staff.staff_id,
        filename="Rebooking_Terms_2026.pdf",
        file_size_bytes=1048576,
        chunk_count=45,
        status="INDEXED",
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)

    assert len(staff.document_uploads) == 1
    assert staff.document_uploads[0].chunk_count == 45

    # Verify Pydantic DTOs
    staff_dto = StaffDTO.model_validate(staff)
    upload_dto = DocumentUploadDTO.model_validate(upload)
    assert staff_dto.username == "admin_sarah"
    assert upload_dto.status == "INDEXED"


def test_evaluation_scores_persistence(db_session):
    """Verify RAGAS quantitative evaluation score recording."""
    session = Session()
    db_session.add(session)
    db_session.commit()

    conversation = Conversation(session_id=session.session_id, system_variant="RAG")
    db_session.add(conversation)
    db_session.commit()

    eval_score = EvaluationScore(
        conversation_id=conversation.conversation_id,
        system_variant="RAG",
        pillar="Baggage",
        faithfulness_score=0.96,
        answer_relevancy_score=0.92,
        context_recall_score=0.88,
    )
    db_session.add(eval_score)
    db_session.commit()
    db_session.refresh(eval_score)

    assert eval_score.faithfulness_score == 0.96
    eval_dto = EvaluationScoreDTO.model_validate(eval_score)
    assert eval_dto.pillar == "Baggage"
