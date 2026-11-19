"""Ownership of chat history for every role, source links, and the sessions migration."""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document
from sqlalchemy import create_engine, inspect, text

import src.main as main
from src.core.security import hash_password
from src.models.entities import StaffAccount

VISA = "Kenya Airways _ Visa and Health Information.html"
ALLOWANCE = "Kenya Airways _ Baggage Allowance.html"
HAND = "Hand Baggage Information.html"
CHECKIN = "Kenya Airways PLC _ Online Check-in.html"
FAQS = "Kenya Airways _ FAQs.html"
MEDICAL = "Medical and Special Needs.html"


def _doc(source: str, text_: str = "Policy text.") -> Document:
    return Document(page_content=text_, metadata={"source": source})


def make_staff(factory, username="staff_one", role="policy_admin") -> str:
    with factory() as db:
        staff = StaffAccount(
            username=username,
            password_hash=hash_password("staff-password"),
            full_name=username,
            role=role,
        )
        db.add(staff)
        db.commit()
        db.refresh(staff)
        return staff.staff_id


def staff_headers(client, username) -> dict:
    login = client.post(
        "/auth/staff/login", json={"username": username, "password": "staff-password"}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def passenger_headers(client, email) -> dict:
    registered = client.post(
        "/auth/register", json={"email": email, "password": "passenger-password"}
    )
    assert registered.status_code == 201
    return {"Authorization": f"Bearer {registered.json()['access_token']}"}


class FakeChain:
    def __init__(self, answer: str):
        self.answer = answer

    def invoke(self, payload):
        return SimpleNamespace(content=self.answer)


@pytest.fixture
def rag_stub(monkeypatch, tmp_path):
    """Run /ask/ with a fake retriever and chain; no index, embeddings or LLM."""
    (tmp_path / "index").mkdir()
    (tmp_path / "index" / "marker").write_text("x")
    docs = [_doc(VISA), _doc(ALLOWANCE), _doc(HAND), _doc(CHECKIN), _doc(FAQS)]
    state = {"answer": "Passports are needed [1]. Bags are limited [2].", "docs": docs}
    monkeypatch.setattr(main, "PERSIST_DIR", str(tmp_path / "index"))
    monkeypatch.setattr(main, "Chroma", lambda **kwargs: object())
    monkeypatch.setattr(main, "MiniLMEmbeddings", lambda: object())
    monkeypatch.setattr(
        main, "retrieve_policy_documents", lambda store, q, history: state["docs"]
    )
    monkeypatch.setattr(main, "get_llm_chain", lambda: FakeChain(state["answer"]))
    # These tests cover links and history, so keep the lexical answerability
    # guard out of the way (its own tests live in test_answer_quality_round5.py).
    monkeypatch.setenv("ANSWERABILITY_GUARD", "off")
    monkeypatch.setenv("ANSWER_DETAIL_HINTS", "0")
    return state


def ask(client, question, headers=None, conversation_id=None):
    data = {"question": question}
    if conversation_id:
        data["conversation_id"] = conversation_id
    return client.post("/ask/", data=data, headers=headers or {})


# ---------------------------------------------------------------- ownership


def test_staff_history_lists_only_their_own_conversations(
    client, test_session_factory, rag_stub
):
    make_staff(test_session_factory, "staff_a")
    make_staff(test_session_factory, "staff_b")
    a, b = staff_headers(client, "staff_a"), staff_headers(client, "staff_b")

    conv_a = ask(client, "What documents do I need?", a).json()["conversation_id"]
    conv_b = ask(client, "What is the check-in window?", b).json()["conversation_id"]

    list_a = client.get("/history/conversations", headers=a).json()
    list_b = client.get("/history/conversations", headers=b).json()
    assert [c["conversation_id"] for c in list_a] == [conv_a]
    assert [c["conversation_id"] for c in list_b] == [conv_b]


def test_staff_cannot_read_another_users_conversation(
    client, test_session_factory, rag_stub
):
    make_staff(test_session_factory, "staff_a")
    make_staff(test_session_factory, "staff_b", role="super_admin")
    a, b = staff_headers(client, "staff_a"), staff_headers(client, "staff_b")
    passenger = passenger_headers(client, "someone@example.com")

    staff_conv = ask(client, "Staff question", a).json()["conversation_id"]
    passenger_conv = ask(client, "Passenger question", passenger).json()[
        "conversation_id"
    ]

    # Another staff member (even a super_admin) and a passenger get 404, not the chat.
    assert client.get(f"/history/conversations/{staff_conv}", headers=b).status_code == 404
    assert (
        client.get(f"/history/conversations/{staff_conv}", headers=passenger).status_code
        == 404
    )
    # Staff cannot read a passenger's chat either.
    assert (
        client.get(f"/history/conversations/{passenger_conv}", headers=a).status_code
        == 404
    )
    # The owner can.
    owner_view = client.get(f"/history/conversations/{staff_conv}", headers=a)
    assert owner_view.status_code == 200
    assert [m["role"] for m in owner_view.json()["messages"]] == ["user", "assistant"]


def test_staff_cannot_continue_another_users_conversation(
    client, test_session_factory, rag_stub
):
    make_staff(test_session_factory, "staff_a")
    make_staff(test_session_factory, "staff_b")
    a, b = staff_headers(client, "staff_a"), staff_headers(client, "staff_b")
    conv = ask(client, "First", a).json()["conversation_id"]
    assert ask(client, "Hijack", b, conversation_id=conv).status_code == 404


def test_passenger_history_unchanged_and_requires_login(client, rag_stub):
    owner = passenger_headers(client, "owner@example.com")
    other = passenger_headers(client, "other@example.com")
    conv = ask(client, "Mine", owner).json()["conversation_id"]
    assert client.get("/history/conversations").status_code == 401
    assert client.get("/history/conversations", headers=other).json() == []
    assert (
        client.get(f"/history/conversations/{conv}", headers=other).status_code == 404
    )
    assert [
        c["conversation_id"]
        for c in client.get("/history/conversations", headers=owner).json()
    ] == [conv]


# -------------------------------------------------------------- source links


def test_ask_returns_only_cited_pages_as_links(client, rag_stub):
    body = ask(client, "What documents do I need for a flight?").json()
    links = body["source_links"]
    assert [link["file"] for link in links] == [VISA, ALLOWANCE]
    assert all(link["url"].startswith("https://www.kenya-airways.com/") for link in links)
    assert links[0]["title"] == "Visa and Health Information"
    # Old fields remain for evaluation and old clients.
    assert body["sources"] == [VISA, ALLOWANCE]
    assert len(body["citations"]) == 5
    assert "[1]" not in body["response"] and "[2]" not in body["response"]


def test_source_links_are_capped_at_four_and_deduplicated(client, rag_stub):
    rag_stub["docs"] = [
        _doc(VISA),
        _doc(VISA, "Another chunk from the same page."),
        _doc(ALLOWANCE),
        _doc(HAND),
        _doc(CHECKIN),
        _doc(FAQS),
    ]
    rag_stub["answer"] = "A [1][2][3][4][5][6]."
    links = ask(client, "q").json()["source_links"]
    assert len(links) == 4
    assert len({link["file"] for link in links}) == 4


def test_not_found_answer_has_no_links(client, rag_stub):
    rag_stub["answer"] = "I couldn't find that in the Kenya Airways pages I have."
    assert ask(client, "Unanswerable?").json()["source_links"] == []


def test_uncited_answer_has_no_links(client, rag_stub):
    rag_stub["answer"] = "A plain answer without markers."
    assert ask(client, "q").json()["source_links"] == []


def test_booking_handoff_returns_official_page_link(client, rag_stub):
    body = ask(client, "How do I book a flight?").json()
    assert [link["url"] for link in body["source_links"]] == [
        "https://www.kenya-airways.com/en-us/book-a-flight/"
    ]


def test_saved_history_restores_links_for_used_pages_only(
    client, test_session_factory, rag_stub
):
    make_staff(test_session_factory, "staff_a")
    headers = staff_headers(client, "staff_a")
    first = ask(client, "What documents do I need?", headers).json()
    detail = client.get(
        f"/history/conversations/{first['conversation_id']}", headers=headers
    ).json()
    user_msg, assistant_msg = detail["messages"]
    assert user_msg["source_links"] == []
    saved = [(link["file"], link["url"]) for link in assistant_msg["source_links"]]
    assert saved == [(link["file"], link["url"]) for link in first["source_links"]]
    assert {m["document_source"] for m in assistant_msg["retrieval_metadata"]} == {
        VISA,
        ALLOWANCE,
    }


def test_saved_history_restores_booking_link(client, rag_stub):
    headers = passenger_headers(client, "booker@example.com")
    first = ask(client, "How do I book a flight?", headers).json()
    detail = client.get(
        f"/history/conversations/{first['conversation_id']}", headers=headers
    ).json()
    links = detail["messages"][1]["source_links"]
    assert [link["url"] for link in links] == [
        "https://www.kenya-airways.com/en-us/book-a-flight/"
    ]


# --------------------------------------------------------------- migration


def test_sessions_migration_adds_staff_id_and_is_idempotent(monkeypatch, tmp_path):
    """Old Neon-style `sessions` table (no staff_id) is upgraded without data loss."""
    import src.core.database as database

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE sessions (session_id VARCHAR(36) PRIMARY KEY, "
                "passenger_id VARCHAR(36), created_at DATETIME, last_active DATETIME)"
            )
        )
        connection.execute(
            text("INSERT INTO sessions (session_id, passenger_id) VALUES ('s1', 'p1')")
        )
    monkeypatch.setattr(database, "engine", engine)

    database.init_db()
    database.init_db()  # second run must be a no-op, not an error

    columns = {c["name"] for c in inspect(engine).get_columns("sessions")}
    indexes = {i["name"] for i in inspect(engine).get_indexes("sessions")}
    assert "staff_id" in columns
    assert "ix_sessions_staff_id" in indexes
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT passenger_id, staff_id FROM sessions WHERE session_id='s1'")
        ).one()
    assert tuple(row) == ("p1", None)
    engine.dispose()
