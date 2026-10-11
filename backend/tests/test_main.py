"""Unit tests for backend main entrypoint."""

import os
from unittest import mock

from src.main import get_application_status


def test_get_application_status_default():
    """Test default application status output."""
    status = get_application_status()
    assert status["status"] in ["healthy", "online"]
    assert status["service"] == "rag-backend"


def test_get_application_status_custom_env():
    """Test custom environment detection."""
    with mock.patch.dict(os.environ, {"APP_ENV": "staging"}):
        status = get_application_status()
        assert status["environment"] == "staging"
