"""FastAPI application endpoints for Airline Customer Support RAG with RBAC, Auth, and DB persistence."""

import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_chroma import Chroma
from sqlalchemy.orm import Session
from src.core.auth import (
    AuthUser,
    get_current_user,
    get_current_user_optional,
    require_role,
)
from src.core.database import SessionLocal, get_db, init_db
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
from src.schemas.auth import (
    ConversationHistoryDetail,
    ConversationHistorySummary,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)
from src.schemas.chat import MessageDTO, RetrievalMetadataDTO

from .logger import logger
from .modules.llm import get_llm_chain
from .modules.load_vesctorstore import PERSIST_DIR, load_vectorstore
from .modules.query_handlers import query_chain


def seed_default_accounts():
    """Seed demo staff accounts in development only."""
    if os.getenv("APP_ENV", "production").lower() != "development":
        logger.info("Skipping demo staff account seed outside development")
        return

    db = SessionLocal()
    try:
        # 1. Super Admin
        admin = db.query(StaffAccount).filter(StaffAccount.username == "admin").first()
        if not admin:
            admin = StaffAccount(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="System Administrator",
                role="super_admin",
            )
            db.add(admin)

        # 2. Policy Admin Staff
        staff = db.query(StaffAccount).filter(StaffAccount.username == "staff").first()
        if not staff:
            staff = StaffAccount(
                username="staff",
                password_hash=hash_password("staff123"),
                full_name="Airline Support Staff",
                role="policy_admin",
            )
            db.add(staff)

        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize tables and seed development demo accounts on startup."""
    init_db()
    seed_default_accounts()
    yield


app = FastAPI(
    title="Airline Customer Support RAG API",
    description="Conversational AI platform for airline policy support with RBAC and persistence",
    version="0.2.0",
    lifespan=lifespan,
)

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


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "online", "service": "Airline Customer Support RAG API"}


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


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates both passengers (via email) and staff members (via username)."""
    # 1. Check Passenger Account
    passenger = (
        db.query(PassengerAccount)
        .filter(PassengerAccount.email == payload.username_or_email)
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

    # 2. Check Staff Account
    staff = (
        db.query(StaffAccount)
        .filter(StaffAccount.username == payload.username_or_email)
        .first()
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
        detail="Invalid credentials. Please verify your email/username and password.",
    )


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
    """Accepts policy PDF files, parses, chunks, embeds, and logs into PostgreSQL audit trail."""
    try:
        logger.info(f"Staff '{current_user.identifier}' uploading {len(files)} files")
        load_vectorstore(files)

        # Log uploads in database
        indexed_files = []
        for file in files:
            file_size = None
            if hasattr(file, "size"):
                file_size = file.size

            upload_record = DocumentUpload(
                staff_id=current_user.user_id,
                filename=file.filename,
                file_size_bytes=file_size,
                chunk_count=0,
                status="INDEXED",
            )
            db.add(upload_record)
            indexed_files.append(file.filename)

        db.commit()
        logger.info(
            "Documents successfully indexed into ChromaDB and recorded in database"
        )

        return {
            "message": "Files processed and indexed into knowledge base successfully.",
            "files_indexed": indexed_files,
            "uploaded_by": current_user.identifier,
        }
    except Exception as e:
        logger.error(f"Error processing files: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


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
            db_session = DbSession(passenger_id=passenger_id)
            db.add(db_session)
            db.commit()
            db.refresh(db_session)

            conv = Conversation(session_id=db_session.session_id, system_variant="RAG")
            db.add(conv)
            db.commit()
            db.refresh(conv)

        # 2. Record User Message
        user_msg = Message(
            conversation_id=conv.conversation_id,
            role="user",
            content=question,
        )
        db.add(user_msg)
        db.commit()

        # 3. Retrieve Context from ChromaDB
        context = ""
        source_docs = []
        if os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR):
            vectorstore = Chroma(
                persist_directory=PERSIST_DIR,
                embedding_function=MiniLMEmbeddings(),
            )
            source_docs = vectorstore.similarity_search(question, k=4)
            context = "\n\n---\n\n".join(doc.page_content for doc in source_docs)

        # 4. Generate Answer via Groq LLM
        chain = get_llm_chain()
        result = query_chain(chain, question, context=context, source_docs=source_docs)
        answer_text = result.get("response", "")

        # 5. Record Assistant Message
        assistant_msg = Message(
            conversation_id=conv.conversation_id,
            role="assistant",
            content=answer_text,
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
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
