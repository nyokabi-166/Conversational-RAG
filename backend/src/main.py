"""FastAPI application endpoints for Airline Customer Support RAG."""

import os
from typing import List
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_chroma import Chroma
from src.rag_pipeline import MiniLMEmbeddings
from .logger import logger
from .modules.llm import get_llm_chain
from .modules.load_vesctorstore import PERSIST_DIR, load_vectorstore
from .modules.query_handlers import query_chain

app = FastAPI(
    title="Airline Customer Support RAG API",
    description="Conversational AI platform for airline policy support",
    version="0.1.0",
)

# Allow frontend CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def catch_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("UNHANDLED_EXCEPTION")
        return JSONResponse(content={"error": str(exc)}, status_code=500)


@app.get("/")
def root():
    """Health check / root endpoint."""
    return {"status": "online", "service": "Airline Customer Support RAG API"}


@app.post("/upload_pdfs/")
async def upload_pdfs(files: List[UploadFile] = File(...)):
    """Accepts policy PDF files, parses, chunks, embeds, and persists into ChromaDB."""
    try:
        logger.info(f"Received {len(files)} files for indexing")
        vectorstore = load_vectorstore(files)
        logger.info("Documents successfully indexed into ChromaDB")
        return {
            "message": "Files processed and ChromaDB vector store updated successfully",
            "files_indexed": [f.filename for f in files],
        }
    except Exception as e:
        logger.error(f"Error processing files: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/ask/")
async def ask_question(question: str = Form(...)):
    """Retrieves relevant policy chunks from ChromaDB and generates an answer via Groq LLM."""
    try:
        logger.info(f"User query received: {question}")
        context = ""
        source_docs = []

        # Retrieve relevant chunks from ChromaDB if it exists and has content
        if os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR):
            vectorstore = Chroma(
                persist_directory=PERSIST_DIR,
                embedding_function=MiniLMEmbeddings(),
            )
            source_docs = vectorstore.similarity_search(question, k=4)
            context = "\n\n---\n\n".join(doc.page_content for doc in source_docs)

        chain = get_llm_chain()
        result = query_chain(chain, question, context=context, source_docs=source_docs)
        logger.info("Query answered successfully")
        return result
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
