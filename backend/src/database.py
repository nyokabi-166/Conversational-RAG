"""Compatibility exports for the application's shared database configuration."""

from src.core.database import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
