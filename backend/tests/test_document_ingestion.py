"""Tests for safe PDF/HTML document validation and indexing."""

from io import BytesIO

import pytest
from fastapi import UploadFile
from langchain_core.documents import Document

import src.modules.load_vesctorstore as ingestion
from src.modules.query_handlers import build_retrieval_query, query_chain


def make_upload(filename, content):
    return UploadFile(filename=filename, file=BytesIO(content))


def test_html_upload_is_sanitized_extracted_and_indexed(tmp_path, monkeypatch):
    html = (
        b"<html><body><h1>Baggage policy</h1><p>Two checked bags.</p>"
        b"<script>privateScriptContent()</script></body></html>"
    )
    prepared = ingestion.validate_uploaded_files(
        [make_upload("../../policy.html", html)]
    )
    captured = {}

    class FakeChroma:
        def __init__(self, persist_directory, embedding_function):
            captured["persist_directory"] = persist_directory
            captured["embedding"] = embedding_function

        def delete(self, where):
            captured["deleted"] = where

        def add_documents(self, documents):
            captured["documents"] = documents

    monkeypatch.setattr(ingestion, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(ingestion, "PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(ingestion, "MiniLMEmbeddings", lambda: object())
    monkeypatch.setattr(ingestion, "Chroma", FakeChroma)

    result = ingestion.load_vectorstore(prepared)

    assert result == [("policy.html", 1)]
    assert len(captured["documents"]) == 1
    document = captured["documents"][0]
    assert "Baggage policy" in document.page_content
    assert "Two checked bags" in document.page_content
    assert "privateScriptContent" not in document.page_content
    assert document.metadata["source"] == "policy.html"
    saved_files = list((tmp_path / "uploads").iterdir())
    assert len(saved_files) == 1
    assert saved_files[0].name.endswith("_policy.html")


def test_invalid_pdf_signature_is_rejected():
    with pytest.raises(ingestion.UploadValidationError) as error:
        ingestion.validate_uploaded_files([make_upload("policy.pdf", b"not a PDF")])

    assert error.value.status_code == 400
    assert error.value.filename == "policy.pdf"


def test_oversized_document_is_rejected(monkeypatch):
    monkeypatch.setattr(ingestion, "MAX_UPLOAD_SIZE_BYTES", 8)

    with pytest.raises(ingestion.UploadValidationError) as error:
        ingestion.validate_uploaded_files(
            [make_upload("policy.html", b"<p>too large</p>")]
        )

    assert error.value.status_code == 413


def test_query_chain_formats_conversation_history_as_chat_messages():
    class FakeChain:
        def invoke(self, payload):
            self.payload = payload
            return "Answer"

    chain = FakeChain()
    result = query_chain(
        chain,
        "Does that include carry-on?",
        context="Baggage policy context",
        conversation_history=[
            ("user", "What is my baggage allowance?"),
            ("assistant", "Two checked bags."),
        ],
    )

    assert result["response"] == "Answer"
    assert [message.type for message in chain.payload["chat_history"]] == [
        "human",
        "ai",
    ]
    assert [message.content for message in chain.payload["chat_history"]] == [
        "What is my baggage allowance?",
        "Two checked bags.",
    ]


def test_retrieval_query_includes_recent_passenger_questions():
    retrieval_query = build_retrieval_query(
        "Does that include carry-on?",
        [
            ("user", "What is my baggage allowance?"),
            ("assistant", "Two checked bags."),
            ("user", "How many checked bags are included?"),
        ],
    )

    assert retrieval_query == (
        "What is my baggage allowance?\n"
        "How many checked bags are included?\n"
        "Does that include carry-on?"
    )
