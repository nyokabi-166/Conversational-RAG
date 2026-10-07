# 🧠 RAG Backend Service

FastAPI backend service for airline customer support conversational AI, providing document ingestion, vector retrieval with ChromaDB, and generation with Groq / Llama 3.

## 🚀 Setup & Execution

```bash
# Install dependencies into virtualenv
poetry install --with dev

# Run locally
poetry run python -m src.main
```

## 🧪 Testing & Linting

```bash
poetry run pytest --cov=src tests/
poetry run flake8 .
poetry run black --check .
```
