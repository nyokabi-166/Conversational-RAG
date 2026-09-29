# ⚡ Conversational RAG (Full-Stack Monorepo)

[![CI Pipeline](https://github.com/nyokabi-166/Conversational-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/nyokabi-166/Conversational-RAG/actions/workflows/ci.yml)
[![Docker Build & Publish](https://github.com/nyokabi-166/Conversational-RAG/actions/workflows/docker.yml/badge.svg)](https://github.com/nyokabi-166/Conversational-RAG/actions/workflows/docker.yml)
[![CodeQL Security Scan](https://github.com/nyokabi-166/Conversational-RAG/actions/workflows/codeql.yml/badge.svg)](https://github.com/nyokabi-166/Conversational-RAG/actions/workflows/codeql.yml)
[![Next.js](https://img.shields.io/badge/frontend-Next.js%2014-black.svg)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/backend-Python%203.11%2B-blue.svg)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/packaging-poetry-cyan.svg)](https://python-poetry.org/)
[![Docker Compose](https://img.shields.io/badge/orchestration-Docker%20Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade, full-stack Conversational Retrieval-Augmented Generation (RAG) platform with an interactive **Next.js (React/TypeScript)** interface and a high-performance **Python backend** equipped with enterprise CI/CD automation.

---

## 📁 Monorepo Architecture

```text
c:/Projects/RAG project/
├── .github/
│   ├── ISSUE_TEMPLATE/            # Bug report & feature request forms
│   ├── workflows/
│   │   ├── ci.yml                 # Dual CI: Backend (Poetry/Pytest) & Frontend (Next.js/ESLint)
│   │   ├── docker.yml             # Builds & publishes both Backend & Frontend containers to GHCR
│   │   └── codeql.yml             # Dual SAST: Python & JavaScript/TypeScript scanning
│   ├── dependabot.yml             # Monorepo dependency updater (/backend, /frontend, /)
│   └── pull_request_template.md    # PR review checklist
├── backend/                       # Python RAG Service
│   ├── src/                       # Application business logic
│   ├── tests/                     # Pytest suite
│   ├── Dockerfile                 # Multi-stage non-root Python build
│   ├── pyproject.toml             # Poetry dependencies & tooling
│   └── setup.cfg                  # Flake8 configuration
├── frontend/                      # Next.js 14 Web Application
│   ├── src/app/                   # App Router, layouts, conversational UI
│   ├── Dockerfile                 # Standalone production Next.js build
│   ├── package.json               # Frontend dependencies & scripts
│   ├── tailwind.config.ts         # Tailwind CSS styling
│   └── tsconfig.json              # TypeScript configuration
├── docker-compose.yml             # Local multi-service orchestration
├── .dockerignore
├── .editorconfig
├── .env.example
├── .gitattributes
├── .gitignore
├── Makefile                       # Developer shortcuts
└── README.md
```

---

## 🛠️ Quickstart

### Option A: Full-Stack with Docker Compose (Recommended)

Run both the Python backend and Next.js frontend with a single command:

```bash
# 1. Copy environment variables template
cp .env.example .env

# 2. Build and launch services
docker compose up --build
```
- **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)

---

### Option B: Local Development

#### 1. Backend Setup (Python & Poetry)
```bash
cd backend
poetry install --with dev
poetry run python -m src.main
```

#### 2. Frontend Setup (Next.js & Node.js)
```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Testing & Code Quality

```bash
# Run backend pytest suite with coverage
cd backend && poetry run pytest --cov=src tests/

# Run backend linters
cd backend && poetry run flake8 . && poetry run black --check .

# Run frontend linter
cd frontend && npm run lint
```
