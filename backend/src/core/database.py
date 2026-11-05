"""Database connection and session management.

Supports PostgreSQL in production / Docker / Laragon, with automatic
fallback to SQLite for frictionless local development.
"""

import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, declarative_base, sessionmaker

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
    """Creates registered tables and applies additive local schema upgrades."""
    # Ensure all models are imported prior to table creation
    import src.models.entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session_columns = {
        column["name"] for column in inspect(engine).get_columns("sessions")
    }
    if "staff_id" not in session_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE sessions ADD COLUMN staff_id VARCHAR(36) "
                "REFERENCES staff_accounts(staff_id) ON DELETE CASCADE"
            )
    session_indexes = {
        index["name"] for index in inspect(engine).get_indexes("sessions")
    }
    if "ix_sessions_staff_id" not in session_indexes:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE INDEX ix_sessions_staff_id ON sessions (staff_id)"
            )
