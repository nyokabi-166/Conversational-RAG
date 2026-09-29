# ⚡ Production RAG System

[![CI Pipeline](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![Docker Build & Publish](https://github.com/OWNER/REPO/actions/workflows/docker.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/docker.yml)
[![CodeQL Security Scan](https://github.com/OWNER/REPO/actions/workflows/codeql.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/codeql.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/packaging-poetry-cyan.svg)](https://python-poetry.org/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready Retrieval-Augmented Generation (RAG) project template equipped with enterprise GitHub CI/CD automation, automated Docker packaging, security scanning, and Python engineering standards.

---

## 🚀 Key Features & Automation

- 🤖 **Continuous Integration (CI)**: Automated multi-version Python testing matrix (3.11, 3.12), test coverage reporting (`pytest`), code formatting check (`black`, `isort`), and linting (`flake8`).
- 🐳 **Automated Docker CI/CD**: Multi-stage, non-root container builds with Buildx and GitHub Actions caching; automatically published to GitHub Container Registry (`ghcr.io`).
- 🛡️ **Continuous Security**: Weekly and PR-level **CodeQL** static application security testing (SAST) and automated vulnerability updates via **Dependabot**.
- 📋 **GitHub Standards**: Standardized YAML Issue Forms for bugs and feature requests, structured Pull Request template, and `CONTRIBUTING.md`.
- 📦 **Modern Dependency Management**: Deterministic dependency locking and packaging via [Poetry](https://python-poetry.org/).

---

## 📁 Repository Structure

```text
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml       # Interactive YAML form for reporting bugs
│   │   ├── feature_request.yml  # Interactive YAML form for feature requests
│   │   └── config.yml           # Issue configuration & community links
│   ├── workflows/
│   │   ├── ci.yml               # Lint, format check, and pytest matrix
│   │   ├── docker.yml           # Build & push Docker images to GHCR
│   │   └── codeql.yml           # Automated CodeQL security scanning
│   ├── dependabot.yml           # Weekly automated dependency & action updates
│   └── pull_request_template.md # Professional PR review checklist
├── src/                         # Application source code
│   ├── __init__.py
│   └── main.py
├── tests/                       # Automated test suite
│   ├── __init__.py
│   └── test_main.py
├── .dockerignore                # Build context exclusions
├── .editorconfig                # Universal indentation and formatting rules
├── .env.example                 # Environment variables template
├── .gitattributes               # Cross-platform LF/CRLF normalization
├── .gitignore                   # Ignores venvs, secrets, cache, and vector DBs
├── CONTRIBUTING.md              # Contribution standards and Git workflow
├── Dockerfile                   # Multi-stage, secure non-root Dockerfile
├── Makefile                     # Developer shortcuts for CLI tasks
├── pyproject.toml               # Poetry dependencies and tool configurations
├── README.md                    # Project documentation
├── SECURITY.md                  # Vulnerability disclosure policy
└── setup.cfg                    # Flake8 configuration
```

---

## 🛠️ Quickstart

### 1. Prerequisites
- [Python 3.11+](https://www.python.org/downloads/)
- [Poetry](https://python-poetry.org/docs/#installation)
- [Docker](https://docs.docker.com/get-docker/) (optional)

### 2. Local Setup
```bash
# 1. Install dependencies into virtualenv
poetry install --with dev

# 2. Configure environment variables
cp .env.example .env
```

### 3. Run Application
```bash
poetry run python -m src.main
```

---

## 🧪 Testing & Code Quality

```bash
# Run full test suite with coverage
poetry run pytest --cov=src tests/

# Check formatting and linting
poetry run black --check .
poetry run isort --check-only .
poetry run flake8 .

# Automatically reformat code
poetry run black .
poetry run isort .
```

---

## 🐳 Docker Deployment

Build and run the container locally:

```bash
# Build production image
docker build -t rag-project:latest .

# Run container with environment configuration
docker run -p 8000:8000 --env-file .env rag-project:latest
```

The GitHub Actions workflow (`docker.yml`) also automatically builds and pushes images to **GitHub Container Registry (GHCR)**:
```bash
docker pull ghcr.io/<owner>/rag-project:latest
```

---

## 🛡️ Security & Dependabot

- **Dependabot** checks weekly for updates to GitHub Actions, Python packages, and Docker base images.
- **CodeQL** scans every PR and push to `main` for security vulnerabilities and injection risks.
- For vulnerability reports, see [SECURITY.md](SECURITY.md).
