"""Unit tests for RAG application entrypoint."""

import os
from unittest import mock

from src.main import get_application_status


def test_get_application_status_default():
    """Test default application status output."""
    status = get_application_status()
    assert status["status"] == "healthy"
    assert status["service"] == "rag-project"


def test_get_application_status_custom_env():
    """Test status reflects custom APP_ENV."""
    with mock.patch.dict(os.environ, {"APP_ENV": "production"}):
        status = get_application_status()
        assert status["environment"] == "production"
