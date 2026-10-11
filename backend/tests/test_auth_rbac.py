"""Integration tests for Authentication, Role-Based Access Control (RBAC), and Database Persistence."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from src.core.database import SessionLocal, init_db
from src.main import app, seed_default_accounts
from src.models.entities import DocumentUpload, Message, PassengerAccount, Session as DbSession

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables and default accounts exist before tests."""
    init_db()
    seed_default_accounts()
    yield


def test_passenger_register_and_login():
    """Test full passenger registration and login flow."""
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"passenger_{unique_suffix}@strathmore.edu"
    password = "secretpassword123"

    # 1. Register
    reg_res = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Jane Strathmore"},
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["role"] == "passenger"

    # 2. Login
    login_res = client.post(
        "/auth/login",
        json={"username_or_email": email, "password": password},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["role"] == "passenger"
    token = login_data["access_token"]

    # 3. Check /auth/me
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["identifier"] == email


def test_staff_login_and_rbac_upload_protection():
    """Verify that only staff members (policy_admin) can upload PDFs; passengers are forbidden."""
    # 1. Login as Staff
    staff_res = client.post(
        "/auth/login",
        json={"username_or_email": "staff", "password": "staff123"},
    )
    assert staff_res.status_code == 200
    staff_token = staff_res.json()["access_token"]

    # 2. Register and login as a Passenger
    p_email = f"passenger_{str(uuid.uuid4())[:8]}@gmail.com"
    pass_res = client.post(
        "/auth/register",
        json={"email": p_email, "password": "pass1234password"},
    )
    assert pass_res.status_code == 201
    pass_login = client.post(
        "/auth/login",
        json={"username_or_email": p_email, "password": "pass1234password"},
    )
    pass_token = pass_login.json()["access_token"]

    # Create dummy PDF bytes
    dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy pdf bytes")

    # 3. Passenger attempts to upload -> MUST RETURN 403 FORBIDDEN!
    forbidden_res = client.post(
        "/upload_pdfs/",
        files={"files": ("test_policy.pdf", dummy_pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {pass_token}"},
    )
    assert forbidden_res.status_code == 403
    assert "lacks permissions" in forbidden_res.json()["detail"]

    # 4. Anonymous user (no token) -> MUST RETURN 401 UNAUTHORIZED!
    unauth_res = client.post(
        "/upload_pdfs/",
        files={"files": ("test_policy.pdf", dummy_pdf, "application/pdf")},
    )
    assert unauth_res.status_code == 401

    # 5. Staff attempts to view document audit list -> MUST SUCCEED (200 OK)
    docs_res = client.get("/documents/", headers={"Authorization": f"Bearer {staff_token}"})
    assert docs_res.status_code == 200
    assert isinstance(docs_res.json(), list)


def test_ask_question_and_chat_history_persistence():
    """Verify that asking a question stores conversation and messages, and passenger can view history."""
    email = f"hist_{str(uuid.uuid4())[:8]}@air.com"
    password = "historypassword"

    client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "History Passenger"},
    )
    login_res = client.post(
        "/auth/login",
        json={"username_or_email": email, "password": password},
    )
    token = login_res.json()["access_token"]

    # Ask question with authenticated token
    ask_res = client.post(
        "/ask/",
        data={"question": "What is the pet policy in cabin?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ask_res.status_code == 200
    ask_data = ask_res.json()
    assert "conversation_id" in ask_data
    conv_id = ask_data["conversation_id"]

    # Verify conversation history drawer endpoint
    hist_res = client.get("/history/conversations", headers={"Authorization": f"Bearer {token}"})
    assert hist_res.status_code == 200
    hist_list = hist_res.json()
    assert len(hist_list) >= 1
    assert any(h["conversation_id"] == conv_id for h in hist_list)

    # Verify conversation detail endpoint
    detail_res = client.get(f"/history/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert len(detail_data["messages"]) >= 2  # user message and assistant response
    assert detail_data["messages"][0]["role"] == "user"
    assert detail_data["messages"][1]["role"] == "assistant"
