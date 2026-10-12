"""Automated integration tests for FastAPI RAG endpoints."""

from src.core.security import hash_password
from src.main import app
from src.models.entities import StaffAccount


def test_root_health_check(client):
    """Verify GET / returns 200 OK with service status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["online", "healthy"]


def test_ask_endpoint(client, monkeypatch, tmp_path):
    """Verify POST /ask/ returns a structured answer from the LLM."""
    monkeypatch.setattr("src.main.PERSIST_DIR", str(tmp_path / "missing-index"))
    monkeypatch.setattr("src.main.get_llm_chain", lambda: object())
    monkeypatch.setattr(
        "src.main.query_chain",
        lambda chain, question, context, source_docs: {
            "response": "The policy permits two checked bags.",
            "sources": ["baggage-policy.pdf"],
        },
    )
    response = client.post(
        "/ask/", data={"question": "What is the policy for carry-on luggage?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0


def test_upload_and_retrieve_e2e(client, test_session_factory, monkeypatch, tmp_path):
    """Verify authenticated upload and query integration without external services."""
    import src.main as main

    monkeypatch.setattr(main, "load_vectorstore", lambda files: None)
    monkeypatch.setattr(main, "PERSIST_DIR", str(tmp_path / "missing-index"))
    monkeypatch.setattr(main, "get_llm_chain", lambda: object())
    monkeypatch.setattr(
        main,
        "query_chain",
        lambda chain, question, context, source_docs: {
            "response": "Economy passengers receive 2 free checked bags of 23kg each.",
            "sources": ["Kenya_Airways_Policy.pdf"],
        },
    )
    with test_session_factory() as db:
        staff = StaffAccount(
            username="staff",
            password_hash=hash_password("staff123"),
            full_name="Test Staff",
            role="policy_admin",
        )
        db.add(staff)
        db.commit()

    staff_login = client.post(
        "/auth/login",
        json={"username_or_email": "staff", "password": "staff123"},
    )
    assert staff_login.status_code == 200
    token = staff_login.json()["access_token"]

    # 2. Test upload with staff credentials
    upload_res = client.post(
        "/upload_pdfs/",
        files={"files": ("Kenya_Airways_Policy.pdf", b"test pdf", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert "files_indexed" in upload_data

    # 3. Test asking question based on the uploaded rule
    ask_res = client.post(
        "/ask/",
        data={"question": "How many free checked bags do economy passengers receive?"},
    )
    assert ask_res.status_code == 200
    ask_data = ask_res.json()
    assert "response" in ask_data
    assert "2" in ask_data["response"] or "two" in ask_data["response"].lower()
    assert len(ask_data["sources"]) > 0
