"""Authentication and role-based access tests."""

import pytest

from src.core.security import hash_password
from src.main import seed_default_accounts
from src.models.entities import DocumentUpload, StaffAccount


def create_staff(test_session_factory, role="policy_admin"):
    with test_session_factory() as db:
        staff = StaffAccount(
            username=f"{role}_user",
            password_hash=hash_password("staff-password"),
            full_name="Test Staff",
            role=role,
        )
        db.add(staff)
        db.commit()
        db.refresh(staff)
        return staff.staff_id


def test_register_login_and_profile(client):
    registered = client.post(
        "/auth/register",
        json={
            "email": "Passenger@example.com",
            "password": "passenger-password",
            "full_name": "Test Passenger",
        },
    )
    assert registered.status_code == 201
    token = registered.json()["access_token"]
    assert registered.json()["role"] == "passenger"
    profile = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json() == {
        "user_id": registered.json()["user_id"],
        "identifier": "passenger@example.com",
        "role": "passenger",
        "full_name": "Test Passenger",
    }

    login = client.post(
        "/auth/login",
        json={
            "username_or_email": "passenger@example.com",
            "password": "passenger-password",
        },
    )
    assert login.status_code == 200
    assert login.json()["user_id"] == registered.json()["user_id"]


def test_registration_normalizes_email_and_rejects_duplicates(client):
    payload = {"email": "Passenger@example.com", "password": "passenger-password"}
    first = client.post("/auth/register", json=payload)
    second = client.post(
        "/auth/register", json={**payload, "email": "passenger@example.com"}
    )
    assert first.status_code == 201
    assert second.status_code == 400


def test_invalid_credentials_and_tokens_are_rejected(client):
    login = client.post(
        "/auth/login",
        json={"username_or_email": "missing@example.com", "password": "wrong-password"},
    )
    assert login.status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert (
        client.get(
            "/auth/me", headers={"Authorization": "Bearer not-a-valid-token"}
        ).status_code
        == 401
    )


def test_document_routes_require_staff_roles(client, test_session_factory, monkeypatch):
    import src.main as main

    monkeypatch.setattr(
        main,
        "load_vectorstore",
        lambda files: [(upload.filename, 3) for upload in files],
    )
    payload = {
        "files": ("policy.pdf", b"%PDF-1.4\nmocked test document", "application/pdf")
    }

    assert client.post("/upload_pdfs/", files=payload).status_code == 401

    passenger = client.post(
        "/auth/register",
        json={"email": "passenger@example.com", "password": "passenger-password"},
    ).json()
    passenger_headers = {"Authorization": f"Bearer {passenger['access_token']}"}
    assert (
        client.post(
            "/upload_pdfs/", files=payload, headers=passenger_headers
        ).status_code
        == 403
    )
    assert client.get("/documents/", headers=passenger_headers).status_code == 403

    for role in ("policy_admin", "super_admin"):
        create_staff(test_session_factory, role=role)
        login = client.post(
            "/auth/login",
            json={"username_or_email": f"{role}_user", "password": "staff-password"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        uploaded = client.post("/upload_pdfs/", files=payload, headers=headers)
        assert uploaded.status_code == 200
        assert uploaded.json()["files_indexed"] == ["policy.pdf"]
        assert uploaded.json()["chunk_counts"] == [
            {"filename": "policy.pdf", "chunk_count": 3}
        ]
        assert client.get("/documents/", headers=headers).status_code == 200


def test_html_upload_uses_safe_filename_and_records_chunks(
    client, test_session_factory, monkeypatch
):
    import src.main as main

    monkeypatch.setattr(
        main,
        "load_vectorstore",
        lambda files: [(upload.filename, 2) for upload in files],
    )
    staff_id = create_staff(test_session_factory)
    login = client.post(
        "/auth/login",
        json={"username_or_email": "policy_admin_user", "password": "staff-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    uploaded = client.post(
        "/upload_pdfs/",
        files={
            "files": (
                "../../rules.html",
                b"<html><body><h1>Baggage rules</h1></body></html>",
                "text/html",
            )
        },
        headers=headers,
    )

    assert uploaded.status_code == 200
    assert uploaded.json()["files_indexed"] == ["rules.html"]
    with test_session_factory() as db:
        record = db.query(DocumentUpload).one()
        assert record.staff_id == staff_id
        assert record.filename == "rules.html"
        assert record.file_size_bytes > 0
        assert record.chunk_count == 2
        assert record.status == "INDEXED"


def test_unsupported_upload_is_rejected_and_logged(
    client, test_session_factory, monkeypatch
):
    staff_id = create_staff(test_session_factory)
    login = client.post(
        "/auth/login",
        json={"username_or_email": "policy_admin_user", "password": "staff-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/upload_pdfs/",
        files={"files": ("payload.txt", b"not a document", "text/plain")},
        headers=headers,
    )

    assert response.status_code == 400
    with test_session_factory() as db:
        record = db.query(DocumentUpload).one()
        assert record.staff_id == staff_id
        assert record.filename == "payload.txt"
        assert record.status == "FAILED"


def test_failed_indexing_is_logged_without_exposing_internal_errors(
    client, test_session_factory, monkeypatch
):
    import src.main as main

    staff_id = create_staff(test_session_factory)
    login = client.post(
        "/auth/login",
        json={"username_or_email": "policy_admin_user", "password": "staff-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def fail_indexing(_uploads):
        raise RuntimeError("internal storage path")

    monkeypatch.setattr(main, "load_vectorstore", fail_indexing)
    response = client.post(
        "/upload_pdfs/",
        files={
            "files": (
                "policy.pdf",
                b"%PDF-1.4\nvalid signature for mocked parser",
                "application/pdf",
            )
        },
        headers=headers,
    )

    assert response.status_code == 500
    assert "internal storage path" not in response.text
    with test_session_factory() as db:
        record = db.query(DocumentUpload).one()
        assert record.staff_id == staff_id
        assert record.filename == "policy.pdf"
        assert record.status == "FAILED"


@pytest.mark.parametrize("role", ["policy_admin", "super_admin"])
def test_staff_cannot_access_passenger_history(client, test_session_factory, role):
    create_staff(test_session_factory, role=role)
    login = client.post(
        "/auth/login",
        json={"username_or_email": f"{role}_user", "password": "staff-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/history/conversations", headers=headers).status_code == 403


def test_passenger_cannot_continue_another_passengers_conversation(
    client, monkeypatch, tmp_path
):
    import src.main as main

    monkeypatch.setattr(main, "PERSIST_DIR", str(tmp_path / "missing-index"))
    monkeypatch.setattr(main, "get_llm_chain", lambda: object())
    monkeypatch.setattr(
        main,
        "query_chain",
        lambda chain, question, context, source_docs, conversation_history: {
            "response": "A grounded answer.",
            "sources": [],
        },
    )
    owner = client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "owner-password"},
    ).json()
    other = client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "other-password"},
    ).json()
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    first_turn = client.post(
        "/ask/",
        data={"question": "What is the baggage allowance?"},
        headers=owner_headers,
    )
    conversation_id = first_turn.json()["conversation_id"]
    attempted_continuation = client.post(
        "/ask/",
        data={"question": "Can you clarify?", "conversation_id": conversation_id},
        headers=other_headers,
    )

    assert attempted_continuation.status_code == 404
    owner_history = client.get(
        f"/history/conversations/{conversation_id}", headers=owner_headers
    )
    assert owner_history.status_code == 200
    assert len(owner_history.json()["messages"]) == 2


def test_previous_turns_are_sent_to_the_generation_chain(client, monkeypatch, tmp_path):
    import src.main as main

    monkeypatch.setattr(main, "PERSIST_DIR", str(tmp_path / "missing-index"))
    monkeypatch.setattr(main, "get_llm_chain", lambda: object())
    seen_histories = []

    def fake_query(chain, question, context, source_docs, conversation_history):
        seen_histories.append(conversation_history)
        return {"response": f"Answer {len(seen_histories)}", "sources": []}

    monkeypatch.setattr(main, "query_chain", fake_query)
    passenger = client.post(
        "/auth/register",
        json={"email": "history@example.com", "password": "history-password"},
    ).json()
    headers = {"Authorization": f"Bearer {passenger['access_token']}"}

    first_turn = client.post(
        "/ask/", data={"question": "What is my baggage allowance?"}, headers=headers
    )
    conversation_id = first_turn.json()["conversation_id"]
    second_turn = client.post(
        "/ask/",
        data={
            "question": "Does that include carry-on?",
            "conversation_id": conversation_id,
        },
        headers=headers,
    )

    assert second_turn.status_code == 200
    assert seen_histories[0] == []
    assert seen_histories[1] == [
        ("user", "What is my baggage allowance?"),
        ("assistant", "Answer 1"),
    ]


def test_demo_staff_accounts_are_not_seeded_outside_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")

    def unexpected_database_access():
        pytest.fail("Non-development startup must not connect to seed demo accounts")

    monkeypatch.setattr("src.main.SessionLocal", unexpected_database_access)
    seed_default_accounts()
