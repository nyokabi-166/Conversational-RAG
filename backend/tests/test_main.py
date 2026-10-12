"""Unit tests for LangChain RAG pipeline components."""

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
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    pipeline = LangChainRAGPipeline()
    assert pipeline.embeddings is not None
    assert pipeline.prompt is not None
    formatted = pipeline.prompt.format(
        context="Economy bags 23kg", question="baggage allowance"
    )
    assert "Economy bags 23kg" in formatted
    assert "baggage allowance" in formatted
