"""
LangChain-based Retrieval-Augmented Generation (RAG) Pipeline.
Aligned with Capstone specifications:
- Document Loader: PyPDFLoader
- Chunking: RecursiveCharacterTextSplitter (chunk_size=500, chunk_overlap=50)
- Embeddings: SentenceTransformer (all-MiniLM-L6-v2)
- Vector Store: ChromaDB
- Generator: Configured OpenAI-compatible model provider with real-time streaming
"""

import os
from typing import Generator, List

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


def SentenceTransformer(model_name: str):
    """Lazy import proxy that keeps the embedding runtime out of API startup."""
    from sentence_transformers import SentenceTransformer as SentenceTransformerClass

    return SentenceTransformerClass(model_name)


class MiniLMEmbeddings(Embeddings):
    """LangChain-compatible embedding wrapper for Sentence Transformers all-MiniLM-L6-v2."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Load the heavyweight embedding runtime only when an embedding operation
        # is actually needed. Importing the API should not initialize Torch.
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        embedding = self.model.encode(text, convert_to_numpy=True)
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
