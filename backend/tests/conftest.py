"""Shared isolated database and API fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.core.database import Base, get_db
from src.main import app
from src.models import entities  # noqa: F401


@pytest.fixture(autouse=True)
def test_auth_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "pytest-only-secret-key-with-more-than-32-characters"
    )


@pytest.fixture
def test_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(test_session_factory):
    def override_get_db():
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        # Avoid the production lifespan, which initializes the developer's configured
        # database; this fixture creates its own schema and only overrides DB access.
        test_client = TestClient(app)
        yield test_client
        test_client.close()
    finally:
        app.dependency_overrides.clear()
