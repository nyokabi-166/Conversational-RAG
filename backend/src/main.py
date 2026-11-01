"""FastAPI application endpoints for Airline Customer Support RAG with RBAC, Auth, and DB persistence."""

import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_chroma import Chroma
from langchain_core.documents import Document
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.auth import (
    AuthUser,
    get_current_user,
    get_current_user_optional,
    require_role,
)
from src.core.database import (  # noqa: F401 - retained for test monkeypatching
    SessionLocal,
    get_db,
    init_db,
)
from src.core.security import create_access_token, hash_password, verify_password
from src.models.entities import (
    Conversation,
    DocumentUpload,
    Message,
    PassengerAccount,
    RetrievalMetadata,
)
from src.models.entities import Session as DbSession
from src.models.entities import StaffAccount
from src.rag_pipeline import MiniLMEmbeddings
from src.routes.flights import router as flights_router
from src.routes.trips import router as trips_router
from src.schemas.auth import (
    ConversationHistoryDetail,
    ConversationHistorySummary,
    PassengerLoginRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)
from src.schemas.chat import MessageDTO, RetrievalMetadataDTO
from src.schemas.staff import (
    AdminBootstrapRequest,
    AdminSetupStatus,
    StaffCreateRequest,
    StaffDTO,
    StaffLoginRequest,
    StaffPasswordResetRequest,
)

from .logger import logger
from .modules.llm import get_llm_chain, get_model_name, get_model_provider
from .modules.load_vesctorstore import (
    PERSIST_DIR,
    UploadValidationError,
    load_vectorstore,
    validate_uploaded_files,
)
from .modules.query_handlers import (
    build_retrieval_queries,
    get_kq_booking_guidance,
    query_chain,
    rank_documents_lexically,
)
from .modules.reminder_worker import start_reminder_worker, stop_reminder_worker


def seed_default_accounts():
    """Keep the old startup hook without creating predictable staff accounts."""
    logger.info("No demo or staff accounts are seeded during startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the application's database tables on startup."""
    init_db()
    seed_default_accounts()
    logger.info(
        "RAG Generation Engine active: Provider=%s, Model=%s",
        get_model_provider(),
        get_model_name(),
    )
    start_reminder_worker()
    yield
    stop_reminder_worker()


app = FastAPI(
    title="Airline Customer Support RAG API",
    description="Conversational AI platform for airline policy support with RBAC and persistence",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(flights_router)
app.include_router(trips_router)

MAX_CONVERSATION_HISTORY_MESSAGES = 10

# Allow frontend CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def catch_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("UNHANDLED_EXCEPTION")
        return JSONResponse(content={"error": str(exc)}, status_code=500)


# =====================================================================
# General Endpoints
# =====================================================================


def get_application_status() -> dict:
    """Return health and environment status."""
    env = os.getenv("APP_ENV", "development")
    return {
        "status": "healthy",
        "environment": env,
        "service": "rag-backend",
        "llm_provider": get_model_provider(),
        "model": get_model_name(),
    }


@app.get("/")
def root():
    """Health check endpoint."""
    return get_application_status()


# =====================================================================
# Authentication & User Management
# =====================================================================


@app.post(
    "/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def register_passenger(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new passenger account and returns an authenticated JWT session."""
    existing = (
        db.query(PassengerAccount)
        .filter(PassengerAccount.email == payload.email)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    passenger = PassengerAccount(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role="passenger",
    )
    db.add(passenger)
    db.commit()
    db.refresh(passenger)

    token = create_access_token(
        data={
            "sub": passenger.passenger_id,
            "user_type": "passenger",
            "role": "passenger",
        }
    )
    return TokenResponse(
        access_token=token,
        user_id=passenger.passenger_id,
        role="passenger",
        identifier=passenger.email,
        full_name=passenger.full_name,
    )


@app.post("/auth/passenger/login", response_model=TokenResponse)
def login_passenger(payload: PassengerLoginRequest, db: Session = Depends(get_db)):
    """Authenticate a passenger using their email address."""
    passenger = (
        db.query(PassengerAccount)
        .filter(PassengerAccount.email == payload.email)
        .first()
    )
    if passenger and verify_password(payload.password, passenger.password_hash):
        token = create_access_token(
            data={
                "sub": passenger.passenger_id,
                "user_type": "passenger",
                "role": passenger.role,
            }
        )
        return TokenResponse(
            access_token=token,
            user_id=passenger.passenger_id,
            role=passenger.role,
            identifier=passenger.email,
            full_name=passenger.full_name,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )


@app.post("/auth/auth0/exchange", response_model=TokenResponse)
def exchange_auth0_token(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
):
    """Validate an Auth0 access token and issue this API's passenger session token."""
    domain = os.getenv("AUTH0_DOMAIN", "").strip().removeprefix("https://").rstrip("/")
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth0 sign-in is not configured on the API.",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Auth0 bearer token is required.",
        )

    request = UrlRequest(
        f"https://{domain}/userinfo",
        headers={"Authorization": authorization, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            identity = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth0 could not verify this sign-in. Please try again.",
        ) from None

    email = identity.get("email")
    subject = identity.get("sub")
    if (
        not isinstance(subject, str)
        or not isinstance(email, str)
        or identity.get("email_verified") is not True
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A verified email address is required for passenger sign-in.",
        )

    normalized_email = email.strip().lower()
    full_name = identity.get("name")
    if not isinstance(full_name, str):
        full_name = None
    passenger = (
        db.query(PassengerAccount)
        .filter(PassengerAccount.email == normalized_email)
        .first()
    )
    if passenger is None:
        passenger = PassengerAccount(
            email=normalized_email,
            full_name=full_name,
            role="passenger",
        )
        db.add(passenger)
        db.commit()
        db.refresh(passenger)
    elif passenger.role != "passenger":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account cannot sign in as a passenger.",
        )
    elif not passenger.full_name and full_name:
        passenger.full_name = full_name
        db.commit()

    token = create_access_token(
        data={
            "sub": passenger.passenger_id,
            "user_type": "passenger",
            "role": "passenger",
        }
    )
    return TokenResponse(
        access_token=token,
        user_id=passenger.passenger_id,
        role="passenger",
        identifier=passenger.email,
        full_name=passenger.full_name,
    )


@app.post("/auth/staff/login", response_model=TokenResponse)
def login_staff(payload: StaffLoginRequest, db: Session = Depends(get_db)):
    """Authenticate a staff member using their username."""
    staff = (
        db.query(StaffAccount).filter(StaffAccount.username == payload.username).first()
    )
    if staff and verify_password(payload.password, staff.password_hash):
        token = create_access_token(
            data={"sub": staff.staff_id, "user_type": "staff", "role": staff.role}
        )
        return TokenResponse(
            access_token=token,
            user_id=staff.staff_id,
            role=staff.role,
            identifier=staff.username,
            full_name=staff.full_name,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid staff username or password.",
    )


@app.get("/auth/admin/setup-status", response_model=AdminSetupStatus)
def get_admin_setup_status(db: Session = Depends(get_db)):
    """Tell the setup screen whether the first administrator can be created."""
    admin_exists = (
        db.query(StaffAccount).filter(StaffAccount.role == "super_admin").first()
        is not None
    )
    return AdminSetupStatus(
        setup_required=not admin_exists,
        setup_enabled=len(os.getenv("ADMIN_SETUP_TOKEN", "")) >= 32,
    )


@app.post("/auth/admin/bootstrap", response_model=TokenResponse)
def bootstrap_first_admin(
    payload: AdminBootstrapRequest, db: Session = Depends(get_db)
):
    """Create the first administrator using a deployment-configured one-time token."""
    configured_token = os.getenv("ADMIN_SETUP_TOKEN", "")
    if len(configured_token) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="First-admin setup is not enabled. Configure ADMIN_SETUP_TOKEN first.",
        )
    if not secrets.compare_digest(payload.setup_token, configured_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The setup token is invalid.",
        )
    admin = db.query(StaffAccount).filter(StaffAccount.role == "super_admin").first()
    if admin:
        if admin.username != payload.username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username does not match the existing administrator.",
            )
        # A configured setup secret also provides a safe recovery path for the
        # original demo admin; it never creates a second administrator.
        admin.password_hash = hash_password(payload.password)
        if payload.full_name:
            admin.full_name = payload.full_name
    else:
        if db.query(StaffAccount).filter_by(username=payload.username).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username is already in use.",
            )
        admin = StaffAccount(
            username=payload.username,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role="super_admin",
        )
        db.add(admin)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An administrator or that username was created at the same time.",
        ) from exc
    db.refresh(admin)
    token = create_access_token(
        data={"sub": admin.staff_id, "user_type": "staff", "role": admin.role}
    )
    return TokenResponse(
        access_token=token,
        user_id=admin.staff_id,
        role=admin.role,
        identifier=admin.username,
        full_name=admin.full_name,
    )


@app.get("/admin/staff", response_model=List[StaffDTO])
def list_staff_accounts(
    current_user: AuthUser = Depends(require_role(["super_admin"])),
    db: Session = Depends(get_db),
):
    """List staff accounts for the administrator's team page."""
    return db.query(StaffAccount).order_by(StaffAccount.created_at.asc()).all()


@app.post("/admin/staff", response_model=StaffDTO, status_code=status.HTTP_201_CREATED)
def create_staff_account(
    payload: StaffCreateRequest,
    current_user: AuthUser = Depends(require_role(["super_admin"])),
    db: Session = Depends(get_db),
):
    """Allow only an administrator to create policy staff accounts."""
    if db.query(StaffAccount).filter_by(username=payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already in use.",
        )
    staff = StaffAccount(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role="policy_admin",
    )
    db.add(staff)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username was created at the same time.",
        ) from exc
    db.refresh(staff)
    return staff


@app.put("/admin/staff/{staff_id}/password", response_model=StaffDTO)
def reset_staff_password(
    staff_id: str,
    payload: StaffPasswordResetRequest,
    current_user: AuthUser = Depends(require_role(["super_admin"])),
    db: Session = Depends(get_db),
):
    """Let an administrator rotate a policy staff member's password."""
    staff = (
        db.query(StaffAccount)
        .filter(StaffAccount.staff_id == staff_id, StaffAccount.role == "policy_admin")
        .first()
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Policy staff account not found.")
    staff.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(staff)
    return staff


@app.get("/auth/me", response_model=UserProfile)
def get_profile(current_user: AuthUser = Depends(get_current_user)):
    """Retrieves current authenticated profile and assigned role."""
    return UserProfile(
        user_id=current_user.user_id,
        identifier=current_user.identifier,
        role=current_user.role,
        full_name=current_user.full_name,
    )


# =====================================================================
# Document Management (RBAC Protected: policy_admin / super_admin)
# =====================================================================


@app.post("/upload_pdfs/")
async def upload_pdfs(
    files: List[UploadFile] = File(...),
    current_user: AuthUser = Depends(require_role(["policy_admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Accept PDF/HTML policy documents and log successful or failed ingestion."""
    try:
        prepared_files = validate_uploaded_files(files)
    except UploadValidationError as exc:
        db.add(
            DocumentUpload(
                staff_id=current_user.user_id,
                filename=exc.filename,
                file_size_bytes=exc.file_size_bytes,
                status="FAILED",
            )
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        logger.info(f"Staff '{current_user.identifier}' uploading {len(files)} files")
        indexed_files = load_vectorstore(prepared_files)

        # Log uploads in database
        for upload, (filename, chunk_count) in zip(prepared_files, indexed_files):
            upload_record = DocumentUpload(
                staff_id=current_user.user_id,
                filename=filename,
                file_size_bytes=len(upload.content),
                chunk_count=chunk_count,
                status="INDEXED",
            )
            db.add(upload_record)

        db.commit()
        logger.info(
            "Documents successfully indexed into ChromaDB and recorded in database"
        )

        return {
            "message": "Files processed and indexed into knowledge base successfully.",
            "files_indexed": [filename for filename, _ in indexed_files],
            "chunk_counts": [
                {"filename": filename, "chunk_count": count}
                for filename, count in indexed_files
            ],
            "uploaded_by": current_user.identifier,
        }
    except Exception:
        db.rollback()
        for upload in prepared_files:
            db.add(
                DocumentUpload(
                    staff_id=current_user.user_id,
                    filename=upload.filename,
                    file_size_bytes=len(upload.content),
                    status="FAILED",
                )
            )
        db.commit()
        logger.exception("Document processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed.",
        )


@app.get("/documents/")
def list_documents(
    current_user: AuthUser = Depends(require_role(["policy_admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Lists all uploaded policy documents with ingestion audit records."""
    records = db.query(DocumentUpload).order_by(DocumentUpload.uploaded_at.desc()).all()
    return [
        {
            "upload_id": r.upload_id,
            "filename": r.filename,
            "file_size_bytes": r.file_size_bytes,
            "chunk_count": r.chunk_count,
            "status": r.status,
            "uploaded_at": r.uploaded_at,
        }
        for r in records
    ]


# =====================================================================
# Passenger Chat History
# =====================================================================


@app.get("/history/conversations", response_model=List[ConversationHistorySummary])
def get_passenger_conversations(
    current_user: AuthUser = Depends(require_role(["passenger"])),
    db: Session = Depends(get_db),
):
    """Retrieves all past conversation threads for the logged-in passenger."""
    # Find all sessions belonging to this passenger
    passenger_sessions = (
        db.query(DbSession).filter(DbSession.passenger_id == current_user.user_id).all()
    )
    session_ids = [s.session_id for s in passenger_sessions]

    conversations = (
        db.query(Conversation)
        .filter(Conversation.session_id.in_(session_ids))
        .order_by(Conversation.created_at.desc())
        .all()
    )

    summaries = []
    for conv in conversations:
        last_msg = conv.messages[-1].content if conv.messages else None
        summaries.append(
            ConversationHistorySummary(
                conversation_id=conv.conversation_id,
                session_id=conv.session_id,
                created_at=conv.created_at,
                system_variant=conv.system_variant,
                message_count=len(conv.messages),
                last_message=last_msg,
            )
        )
    return summaries


@app.get(
    "/history/conversations/{conversation_id}", response_model=ConversationHistoryDetail
)
def get_conversation_detail(
    conversation_id: str,
    current_user: AuthUser = Depends(require_role(["passenger"])),
    db: Session = Depends(get_db),
):
    """Retrieves full dialogue history and citation metadata for a specific conversation."""
    conv = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    session_obj = (
        db.query(DbSession).filter(DbSession.session_id == conv.session_id).first()
    )
    if not session_obj or session_obj.passenger_id != current_user.user_id:
        raise HTTPException(
            status_code=403, detail="Access denied to this conversation."
        )

    message_dtos = []
    for m in conv.messages:
        cit_dtos = [
            RetrievalMetadataDTO(
                retrieval_id=c.retrieval_id,
                message_id=c.message_id,
                chunk_id=c.chunk_id,
                document_source=c.document_source,
                similarity_score=c.similarity_score,
                chunk_text=c.chunk_text,
                retrieved_at=c.retrieved_at,
            )
            for c in m.retrieval_metadata
        ]
        message_dtos.append(
            MessageDTO(
                message_id=m.message_id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                retrieval_metadata=cit_dtos,
            )
        )

    return ConversationHistoryDetail(
        conversation_id=conv.conversation_id,
        session_id=conv.session_id,
        created_at=conv.created_at,
        system_variant=conv.system_variant,
        messages=message_dtos,
    )


# =====================================================================
# RAG Chat & Retrieval (Persisted to Database)
# =====================================================================


@app.post("/ask/")
async def ask_question(
    question: str = Form(...),
    conversation_id: Optional[str] = Form(None),
    current_user: Optional[AuthUser] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Retrieves relevant policy chunks, streams verified answer, and records dialog in PostgreSQL."""
    try:
        logger.info(
            f"Query: '{question}' | User: {current_user.identifier if current_user else 'Guest'}"
        )

        # 1. Resolve or Create Session & Conversation
        passenger_id = (
            current_user.user_id
            if current_user and current_user.role == "passenger"
            else None
        )

        conv = None
        if conversation_id:
            conv = (
                db.query(Conversation)
                .filter(Conversation.conversation_id == conversation_id)
                .first()
            )
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found.",
                )
            owner_session = (
                db.query(DbSession)
                .filter(DbSession.session_id == conv.session_id)
                .first()
            )
            if not owner_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found.",
                )
            if current_user and current_user.role != "passenger":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only passengers can continue passenger conversations.",
                )
            if current_user and owner_session.passenger_id != current_user.user_id:
                # Do not reveal whether a conversation belongs to another passenger.
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found.",
                )
            if not current_user and owner_session.passenger_id is not None:
                # Guest conversation IDs can continue only unowned guest sessions.
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found.",
                )

        if not conv:
            db_session = DbSession(passenger_id=passenger_id)
            db.add(db_session)
            db.commit()
            db.refresh(db_session)

            conv = Conversation(session_id=db_session.session_id, system_variant="RAG")
            db.add(conv)
            db.commit()
            db.refresh(conv)

        previous_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conv.conversation_id)
            .order_by(Message.created_at.desc(), Message.message_id.desc())
            .limit(MAX_CONVERSATION_HISTORY_MESSAGES)
            .all()
        )
        previous_messages.reverse()
        conversation_history = [
            (message.role, message.content)
            for message in previous_messages
            if message.role in {"user", "assistant"}
        ]

        # 2. Record User Message
        user_msg = Message(
            conversation_id=conv.conversation_id,
            role="user",
            content=question,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user_msg)
        db.commit()

        # 3. Retrieve Context from ChromaDB
        context = ""
        source_docs = []
        booking_guidance = get_kq_booking_guidance(question)
        if booking_guidance:
            source_docs = [booking_guidance["document"]]
            context = source_docs[0].page_content
        else:
            retrieval_queries = build_retrieval_queries(question, conversation_history)
        if (
            not booking_guidance
            and os.path.exists(PERSIST_DIR)
            and os.listdir(PERSIST_DIR)
        ):
            vectorstore = Chroma(
                persist_directory=PERSIST_DIR,
                embedding_function=MiniLMEmbeddings(),
            )
            seen_chunks = set()
            indexed = vectorstore.get(include=["documents", "metadatas"])
            indexed_documents = [
                Document(page_content=content, metadata=metadata or {})
                for content, metadata in zip(
                    indexed.get("documents") or [], indexed.get("metadatas") or []
                )
                if content
            ]
            lexical_docs = rank_documents_lexically(
                retrieval_queries[0], indexed_documents, limit=4
            )
            for doc in lexical_docs:
                chunk_key = (doc.metadata.get("source", ""), doc.page_content)
                if chunk_key not in seen_chunks:
                    seen_chunks.add(chunk_key)
                    source_docs.append(doc)
            for retrieval_query in retrieval_queries:
                for doc in vectorstore.similarity_search(retrieval_query, k=4):
                    chunk_key = (
                        doc.metadata.get("source", ""),
                        doc.page_content,
                    )
                    if chunk_key not in seen_chunks:
                        seen_chunks.add(chunk_key)
                        source_docs.append(doc)
                    if len(source_docs) >= 8:
                        break
                if len(source_docs) >= 8:
                    break
            context = "\n\n---\n\n".join(
                f"Source: {doc.metadata.get('source', 'Policy document')}\n"
                f"{doc.page_content}"
                for doc in source_docs
            )
        retrieved_sources = sorted(
            {doc.metadata.get("source", "Unknown source") for doc in source_docs}
        )
        logger.info(
            "Retrieved %d policy chunks from: %s",
            len(source_docs),
            ", ".join(retrieved_sources) if retrieved_sources else "no documents",
        )

        # 4. Use verified official-site steps for the booking hand-off; use RAG for
        # policy and other questions.
        if booking_guidance:
            result = {
                "response": booking_guidance["answer"],
                "sources": [booking_guidance["document"].metadata["source"]],
            }
        else:
            chain = get_llm_chain()
            result = query_chain(
                chain,
                question,
                context=context,
                source_docs=source_docs,
                conversation_history=conversation_history,
            )
        if result.get("error"):
            logger.error("Answer generation failed: %s", result["error"])
            return JSONResponse(
                content={
                    "error": "The assistant could not generate an answer. Please try again in a moment."
                },
                status_code=502,
            )
        answer_text = result.get("response", "")
        if not isinstance(answer_text, str) or not answer_text.strip():
            logger.error("Answer generation produced an empty response.")
            return JSONResponse(
                content={
                    "error": "The assistant returned an empty answer. Please try again."
                },
                status_code=502,
            )

        # 5. Record Assistant Message
        assistant_msg = Message(
            conversation_id=conv.conversation_id,
            role="assistant",
            content=answer_text,
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        # 6. Record Retrieval Citations
        citations_data = []
        for i, doc in enumerate(source_docs):
            doc_source = doc.metadata.get("source", "Policy Document")
            chunk_id = f"{doc_source}_chunk_{i}"
            citation_record = RetrievalMetadata(
                message_id=assistant_msg.message_id,
                chunk_id=chunk_id,
                document_source=doc_source,
                chunk_text=doc.page_content[:300],
            )
            db.add(citation_record)
            citations_data.append(
                {
                    "chunk_id": chunk_id,
                    "document_source": doc_source,
                }
            )
        db.commit()

        return {
            "conversation_id": conv.conversation_id,
            "message_id": assistant_msg.message_id,
            "response": answer_text,
            "sources": result.get("sources", []),
            "citations": citations_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
