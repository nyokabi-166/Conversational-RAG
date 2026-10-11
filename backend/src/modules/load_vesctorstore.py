"""Document ingestion and ChromaDB vector store management."""

import os
from pathlib import Path
from typing import List
from fastapi import UploadFile
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.rag_pipeline import MiniLMEmbeddings

PERSIST_DIR = "./data/chroma_db"
UPLOAD_DIR = "./uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PERSIST_DIR, exist_ok=True)


def load_vectorstore(uploaded_files: List[UploadFile]) -> Chroma:
    """Saves uploaded PDFs, splits them into semantic chunks, and indexes them in ChromaDB."""
    file_paths = []

    for file in uploaded_files:
        save_path = Path(UPLOAD_DIR) / file.filename
        with open(save_path, "wb") as f:
            f.write(file.file.read())
        file_paths.append(str(save_path))

    docs = []
    for path in file_paths:
        loader = PyPDFLoader(path)
        docs.extend(loader.load())

    if not docs:
        raise ValueError("No readable text could be extracted from the uploaded PDF files.")

    # 500-token chunks with 50-token overlap per Capstone specification
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    embeddings = MiniLMEmbeddings()

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
    )

    return vectorstore
