"""Unit tests for LangChain RAG pipeline components."""

import os
from unittest import mock

from src.main import get_application_status
from src.modules import llm as llm_module
from src.rag_pipeline import LangChainRAGPipeline, MiniLMEmbeddings


class FakeVector(list):
    def tolist(self):
        return list(self)


class FakeSentenceTransformer:
    def __init__(self, model_name):
        self.model_name = model_name

    def encode(self, texts, **kwargs):
        if isinstance(texts, list):
            return FakeVector([[0.0] * 384 for _ in texts])
        return FakeVector([0.0] * 384)


def test_get_application_status_default():
    """Test default health status output."""
    status = get_application_status()
    assert status["status"] in ["healthy", "online"]
    assert status["service"] == "rag-backend"


def test_get_application_status_custom_env():
    """Test custom environment detection."""
    with mock.patch.dict(os.environ, {"APP_ENV": "staging"}):
        status = get_application_status()
        assert status["environment"] == "staging"


def test_minilm_embeddings(monkeypatch):
    """Verify the embedding wrapper without downloading a model in CI."""
    monkeypatch.setattr("src.rag_pipeline.SentenceTransformer", FakeSentenceTransformer)
    embedder = MiniLMEmbeddings()
    vector = embedder.embed_query("Kenya Airways baggage policy")
    assert isinstance(vector, list)
    assert len(vector) == 384


def test_rag_pipeline_init(monkeypatch):
    """Verify LangChain pipeline initialization and prompt template."""
    monkeypatch.setattr("src.rag_pipeline.SentenceTransformer", FakeSentenceTransformer)
    monkeypatch.setattr("src.rag_pipeline.load_dotenv", lambda: False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    pipeline = LangChainRAGPipeline()
    assert pipeline.embeddings is not None
    assert pipeline.prompt is not None
    formatted = pipeline.prompt.format(
        context="Economy bags 23kg", question="baggage allowance"
    )
    assert "Economy bags 23kg" in formatted
    assert "baggage allowance" in formatted


def test_get_chat_model_uses_configured_deepinfra_model(monkeypatch):
    """Use the selected DeepInfra model for the shared RAG/baseline factory."""
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("LLM_PROVIDER", "deepinfra")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    monkeypatch.setenv("DEEPINFRA_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo")
    monkeypatch.setattr(llm_module, "ChatOpenAI", FakeChatOpenAI)

    model = llm_module.get_chat_model()

    assert isinstance(model, FakeChatOpenAI)
    assert captured["model"] == "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://api.deepinfra.com/v1/openai"


def test_get_chat_model_requires_openrouter_key(monkeypatch):
    """Fail clearly rather than silently falling back to another provider."""
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    try:
        llm_module.get_chat_model()
    except RuntimeError as exc:
        assert "OPENROUTER_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing OpenRouter credentials to fail")


def test_legacy_pipeline_uses_shared_configured_model(monkeypatch):
    """The alternate pipeline uses the same provider factory as the API/evaluator."""
    model = object()
    monkeypatch.setattr("src.rag_pipeline.SentenceTransformer", FakeSentenceTransformer)
    monkeypatch.setattr("src.rag_pipeline.load_dotenv", lambda: False)
    monkeypatch.setattr("src.rag_pipeline.get_chat_model", lambda: model)
    monkeypatch.setenv("LLM_PROVIDER", "deepinfra")
    monkeypatch.setenv("DEEPINFRA_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo")

    pipeline = LangChainRAGPipeline()

    assert pipeline.llm is model
    assert pipeline.model_name == "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
