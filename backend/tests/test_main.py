"""Unit tests for LangChain RAG pipeline components."""

from src.rag_pipeline import MiniLMEmbeddings, LangChainRAGPipeline


def test_minilm_embeddings():
    """Verify SentenceTransformer embeddings generation."""
    embedder = MiniLMEmbeddings()
    vector = embedder.embed_query("Kenya Airways baggage policy")
    assert isinstance(vector, list)
    assert len(vector) == 384


def test_rag_pipeline_init():
    """Verify LangChain pipeline initialization and prompt template."""
    pipeline = LangChainRAGPipeline()
    assert pipeline.embeddings is not None
    assert pipeline.prompt is not None
    formatted = pipeline.prompt.format(context="Economy bags 23kg", question="baggage allowance")
    assert "Economy bags 23kg" in formatted
    assert "baggage allowance" in formatted
