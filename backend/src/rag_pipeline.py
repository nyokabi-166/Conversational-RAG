"""
LangChain-based Retrieval-Augmented Generation (RAG) Pipeline.
Aligned with Capstone specifications:
- Document Loader: PyPDFLoader
- Chunking: RecursiveCharacterTextSplitter (chunk_size=500, chunk_overlap=50)
- Embeddings: SentenceTransformer (all-MiniLM-L6-v2)
- Vector Store: ChromaDB
- Generator: Configured OpenAI-compatible model provider with real-time streaming
"""

import math
import os
import threading
import time
from typing import Generator, List

import httpx
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate

from src.modules.llm import (
    DEFAULT_DEEPINFRA_MODEL,
    get_chat_model,
    get_model_name,
    get_model_provider,
)


# One loaded model per process. Loading all-MiniLM-L6-v2 takes seconds and hundreds
# of MB, so it must not be repeated for every request.
_MODEL_CACHE: dict = {}
_MODEL_LOCK = threading.Lock()


def SentenceTransformer(model_name: str):
    """Lazy, cached loader that keeps the embedding runtime out of API startup.

    The model is loaded on first use and then reused by every later call.
    """
    model = _MODEL_CACHE.get(model_name)
    if model is None:
        with _MODEL_LOCK:
            model = _MODEL_CACHE.get(model_name)
            if model is None:
                from sentence_transformers import (
                    SentenceTransformer as SentenceTransformerClass,
                )

                model = SentenceTransformerClass(model_name)
                _MODEL_CACHE[model_name] = model
    return model


# ---------------------------------------------------------------------------
# Embedding provider
#   EMBEDDING_PROVIDER=local     (default) sentence-transformers in this process
#   EMBEDDING_PROVIDER=deepinfra DeepInfra's hosted copy of the same model, so the
#                                server never imports PyTorch (small-memory hosts)
# ---------------------------------------------------------------------------
EMBEDDING_PROVIDER_ENV = "EMBEDDING_PROVIDER"
DEEPINFRA_EMBED_URL = "https://api.deepinfra.com/v1/openai/embeddings"
DEFAULT_DEEPINFRA_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384
DEEPINFRA_EMBED_BATCH_SIZE = 64
DEEPINFRA_EMBED_TIMEOUT_SECONDS = 30.0
DEEPINFRA_EMBED_MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

_EMBED_CLIENT = None
_EMBED_CLIENT_LOCK = threading.Lock()


def get_embedding_provider() -> str:
    """Return the configured embedding provider: "local" (default) or "deepinfra"."""
    provider = (os.getenv(EMBEDDING_PROVIDER_ENV) or "local").strip().lower()
    if provider not in {"local", "deepinfra"}:
        raise ValueError(
            f"{EMBEDDING_PROVIDER_ENV} must be 'local' or 'deepinfra', "
            f"got {provider!r}."
        )
    return provider


def _get_embed_client() -> httpx.Client:
    """One shared HTTP client (httpx.Client is thread-safe) to reuse connections."""
    global _EMBED_CLIENT
    if _EMBED_CLIENT is None:
        with _EMBED_CLIENT_LOCK:
            if _EMBED_CLIENT is None:
                _EMBED_CLIENT = httpx.Client(timeout=DEEPINFRA_EMBED_TIMEOUT_SECONDS)
    return _EMBED_CLIENT


def _deepinfra_post(payload: dict, api_key: str) -> httpx.Response:
    return _get_embed_client().post(
        DEEPINFRA_EMBED_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=DEEPINFRA_EMBED_TIMEOUT_SECONDS,
    )


def _parse_embeddings(response, expected_count: int) -> List[List[float]]:
    try:
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        vectors = [row["embedding"] for row in rows]
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            "DeepInfra embeddings returned an unexpected response format."
        ) from exc
    if len(vectors) != expected_count:
        raise RuntimeError(
            f"DeepInfra embeddings returned {len(vectors)} vectors for "
            f"{expected_count} inputs."
        )
    normalised = []
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"DeepInfra embeddings returned {len(vector)}-dimensional vectors; "
                f"expected {EMBEDDING_DIMENSIONS}. Check DEEPINFRA_EMBED_MODEL."
            )
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        normalised.append([float(value) / norm for value in vector])
    return normalised


def _deepinfra_embed_batch(batch: List[str], api_key: str, model: str):
    payload = {"model": model, "input": batch, "encoding_format": "float"}
    last_problem = "unknown error"
    for attempt in range(DEEPINFRA_EMBED_MAX_RETRIES + 1):
        try:
            response = _deepinfra_post(payload, api_key)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_problem = f"network error ({type(exc).__name__})"
        else:
            if response.status_code == 200:
                return _parse_embeddings(response, len(batch))
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                raise RuntimeError(
                    "DeepInfra embeddings request was rejected "
                    f"(HTTP {response.status_code}). Check DEEPINFRA_API_KEY and "
                    "DEEPINFRA_EMBED_MODEL."
                )
            last_problem = f"HTTP {response.status_code}"
        if attempt < DEEPINFRA_EMBED_MAX_RETRIES:
            time.sleep(2**attempt)
    raise RuntimeError(
        f"DeepInfra embeddings failed after {DEEPINFRA_EMBED_MAX_RETRIES + 1} "
        f"attempts ({last_problem})."
    )


def deepinfra_embed(texts: List[str]) -> List[List[float]]:
    """Embed texts with DeepInfra in batches; returns L2-normalised 384-dim vectors."""
    texts = list(texts)
    if not texts:
        return []
    api_key = (os.getenv("DEEPINFRA_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "DEEPINFRA_API_KEY is not set; it is required when "
            f"{EMBEDDING_PROVIDER_ENV}=deepinfra."
        )
    model = (
        os.getenv("DEEPINFRA_EMBED_MODEL") or DEFAULT_DEEPINFRA_EMBED_MODEL
    ).strip()
    vectors: List[List[float]] = []
    for start in range(0, len(texts), DEEPINFRA_EMBED_BATCH_SIZE):
        batch = texts[start : start + DEEPINFRA_EMBED_BATCH_SIZE]
        vectors.extend(_deepinfra_embed_batch(batch, api_key, model))
    return vectors


class MiniLMEmbeddings(Embeddings):
    """LangChain-compatible embeddings for all-MiniLM-L6-v2.

    Uses the local Sentence Transformers model by default, or DeepInfra's hosted
    copy when EMBEDDING_PROVIDER=deepinfra (no PyTorch import in that mode).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        # Default behaviour is unchanged: load the local model up front. In
        # deepinfra mode the heavyweight runtime is never imported.
        if get_embedding_provider() == "local":
            self.model = SentenceTransformer(model_name)

    def _local_model(self):
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        return self.model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if get_embedding_provider() == "deepinfra":
            return deepinfra_embed(texts)
        embeddings = self._local_model().encode(
            texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        if get_embedding_provider() == "deepinfra":
            return deepinfra_embed([text])[0]
        embedding = self._local_model().encode(text, convert_to_numpy=True)
        return embedding.tolist()


class LangChainRAGPipeline:
    """Orchestrates LangChain indexing, retrieval, and configured-model streaming."""

    def __init__(self, model_name: str = DEFAULT_DEEPINFRA_MODEL):
        load_dotenv()
        configured_model = get_model_name()
        self.model_name = configured_model
        if not self.model_name and get_model_provider() == "openrouter":
            self.model_name = model_name
        self.embeddings = MiniLMEmbeddings()
        self.vectorstore: Chroma | None = None
        self.retriever = None

        try:
            self.llm = get_chat_model()
        except RuntimeError as error:
            print(f"[LangChainRAGPipeline] WARNING: {error}")
            self.llm = None

        # Standard RAG prompt template grounded in retrieved context
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a clear, helpful Kenya Airways customer-support "
                        "assistant. Start with the answer the passenger asked for. Be "
                        "concise but complete enough that the passenger can act without "
                        "another turn. Use only "
                        "the supplied policy context for airline-specific facts; never "
                        "guess.\n\n"
                        "Give all relevant general facts even when an exact personal "
                        "answer depends on trip details. Explain briefly how the "
                        "passenger can identify which option applies. Do not ask a "
                        "follow-up question if you can provide a useful answer by "
                        "listing the relevant options or conditions. Ask only when the "
                        "context gives no useful answer without that detail.\n\n"
                        "Read tables by combining each value with its column heading "
                        "and row label. For baggage questions, state the allowance "
                        "values and their route/cabin labels when present. If the "
                        "passenger has not given a route or cabin and the table contains "
                        "several options, show the relevant options and explain that "
                        "their ticket or itinerary determines which applies; do not end "
                        "by asking them to provide it. For broad baggage questions, "
                        "include both checked and cabin allowances when the context "
                        "supplies both.\n\n"
                        "Do not dump long lists or repeat the question. Preserve "
                        "important conditions such as 'may' and 'if required'. If the "
                        "supplied context has no relevant answer, say so plainly and "
                        "suggest the most useful next step.\n\n"
                        "Retrieved policy context:\n{context}"
                    ),
                ),
                ("human", "{question}"),
            ]
        )

    def index_pdf(self, pdf_path: str) -> int:
        """
        Load PDF, split into chunks (~500 tokens with 50-token overlap),
        and index into ChromaDB. Returns the number of chunks indexed.
        """
        # Defer optional ingestion dependencies until an indexing request arrives.
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        # 1. Load document pages
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        # 2. Split into ~500 token chunks with 50 overlap (matching Capstone paper Section 3.2.2)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", " ", ""],
        )
        chunks = splitter.split_documents(pages)

        # 3. Store into ChromaDB vector store
        self.vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
        )
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5},
        )

        return len(chunks)

    def stream_answer(self, query: str) -> Generator[str, None, None]:
        """
        Retrieve relevant chunks from ChromaDB and stream the answer from the configured provider.
        """
        if not self.llm:
            yield "⚠️ Configure the selected LLM provider in `backend/.env` to use chat."
            return

        if not self.retriever:
            yield "⚠️ No document is currently indexed. Please upload a PDF first."
            return

        # 1. Retrieve top-k relevant chunks
        docs = self.retriever.invoke(query)
        context_text = "\n\n---\n\n".join(doc.page_content for doc in docs)

        # 2. Invoke LCEL streaming chain
        chain = self.prompt | self.llm

        try:
            for chunk in chain.stream({"context": context_text, "question": query}):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            provider = get_model_provider().title()
            yield f"⚠️ {provider} API Error: {e}"
