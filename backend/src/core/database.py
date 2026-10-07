"""Database connection and session management.

Supports PostgreSQL in production / Docker / Laragon, with automatic
fallback to SQLite for frictionless local development.
"""

import os
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file_path = (data_dir / "airline_rag.db").resolve()
    DATABASE_URL = f"sqlite:///{db_file_path}"

# SQLite requires check_same_thread=False for multi-threaded/async FastAPI usage
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding transactional database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Creates all registered SQLAlchemy tables if they do not already exist."""
    # Ensure all models are imported prior to table creation
    import src.models.entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
