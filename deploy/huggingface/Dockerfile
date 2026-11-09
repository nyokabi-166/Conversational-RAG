# Hugging Face Spaces (Docker SDK) image for the RAG backend.
# Build context = the staged folder created by deploy.ps1 (src/, kb_index/,
# pyproject.toml, poetry.lock). Spaces expects the app on port 7860 and runs
# the container as uid 1000.

# ==========================================
# Stage 1: Build virtual environment
# ==========================================
FROM python:3.11-slim AS builder

ENV POETRY_VERSION=2.4.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

COPY pyproject.toml poetry.lock* ./

RUN poetry install --no-root --only main

# ==========================================
# Stage 2: Runtime image
# ==========================================
FROM python:3.11-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=7860 \
    HF_HOME=/home/user/.cache/huggingface

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user

WORKDIR /app

COPY --from=builder --chown=user:user /app/.venv /app/.venv
COPY --chown=user:user src/ /app/src/
# Pre-built policy index (Chroma) so the API answers from the real documents.
COPY --chown=user:user kb_index/ /app/data/chroma_db/

RUN mkdir -p /app/uploads && chown user:user /app /app/uploads

USER user

# Download the embedding model at build time so start-up does not depend on
# (or wait for) a download. Same model name the application uses.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 7860

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
