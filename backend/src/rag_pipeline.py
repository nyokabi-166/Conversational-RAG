"""
LangChain-based Retrieval-Augmented Generation (RAG) Pipeline.
Aligned with Capstone specifications:
- Document Loader: PyPDFLoader
- Chunking: RecursiveCharacterTextSplitter (chunk_size=500, chunk_overlap=50)
- Embeddings: SentenceTransformer (all-MiniLM-L6-v2)
- Vector Store: ChromaDB
- Generator: Groq API (ChatGroq) with real-time streaming
"""

import os
from typing import Generator, List
from dotenv import load_dotenv

from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from sentence_transformers import SentenceTransformer


class MiniLMEmbeddings(Embeddings):
    """LangChain-compatible embedding wrapper for Sentence Transformers all-MiniLM-L6-v2."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()


class LangChainRAGPipeline:
    """Orchestrates LangChain document indexing, ChromaDB retrieval, and Groq streaming."""

    def __init__(self, model_name: str = "openai/gpt-oss-20b"):
        load_dotenv()
        self.api_key = os.environ.get("GROQ_API_KEY")
        self.model_name = os.environ.get("GROQ_MODEL", model_name)
        self.embeddings = MiniLMEmbeddings()
        self.vectorstore: Chroma | None = None
        self.retriever = None

        if not self.api_key:
            print("[LangChainRAGPipeline] WARNING: GROQ_API_KEY is not set.")
            self.llm = None
        else:
            self.llm = ChatGroq(
                model=self.model_name,
                api_key=self.api_key,
                temperature=0.2,
            )

        # Standard RAG prompt template grounded in retrieved context
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert customer support assistant for an airline. "
                "Answer the passenger's question accurately based ONLY on the provided policy documents below. "
                "If the answer cannot be found in the context, explicitly respond: "
                "'The document does not contain information on this topic.' "
                "Do not make assumptions or fabricate policies.\n\n"
                "Retrieved Context:\n{context}"
            )),
            ("human", "{question}")
        ])

    def index_pdf(self, pdf_path: str) -> int:
        """
        Load PDF, split into chunks (~500 tokens with 50-token overlap),
        and index into ChromaDB. Returns the number of chunks indexed.
        """
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
        Retrieve relevant chunks from ChromaDB and stream the answer from Groq.
        """
        if not self.llm:
            yield "⚠️ **GROQ_API_KEY is missing!** Please add your key to `backend/.env`."
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
            # Fallback to alternative model if needed
            if "model" in str(e).lower() and self.model_name != "openai/gpt-oss-120b":
                try:
                    fallback_llm = ChatGroq(
                        model="openai/gpt-oss-120b",
                        api_key=self.api_key,
                        temperature=0.2,
                    )
                    fallback_chain = self.prompt | fallback_llm
                    for chunk in fallback_chain.stream({"context": context_text, "question": query}):
                        if chunk.content:
                            yield chunk.content
                    return
                except Exception as fb_err:
                    yield f"⚠️ Groq API Error: {fb_err}"
            else:
                yield f"⚠️ Groq API Error: {e}"
