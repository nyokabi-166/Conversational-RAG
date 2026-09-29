# Contributing to RAG Project

Thank you for your interest in contributing to this project! We welcome contributions, bug fixes, and feature suggestions.

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker (optional, for containerized testing)

### 2. Initial Setup
```bash
# Clone the repository
git clone https://github.com/<owner>/rag-project.git
cd rag-project

# Install dependencies into virtual environment
poetry install --with dev

# Copy environment template
cp .env.example .env
```

---

## 🧪 Testing & Code Quality

Before opening a pull request, ensure your changes pass all local linting and test suites:

```bash
# Format code
poetry run black .
poetry run isort .

# Run linter
poetry run flake8 .

# Run tests with coverage
poetry run pytest --cov=src tests/
```

---

## 🌿 Git & Branching Strategy

1. Create a feature branch off `main`:
   - `feature/description` for new features
   - `fix/description` for bug fixes
   - `docs/description` for documentation improvements
   - `chore/description` for tooling or refactoring

2. Follow **Conventional Commits**:
   - `feat: add hybrid vector search`
   - `fix: resolve token limit truncation in retriever`
   - `docs: update quickstart instructions`
   - `test: add unit tests for reranker`

---

## 🚀 Pull Request Checklist

- [ ] All tests and linters pass locally.
- [ ] Add relevant unit tests for new logic.
- [ ] Follow existing code style and formatting standards.
- [ ] Fill out the Pull Request template completely.
- [ ] Ensure CI pipeline passes cleanly on GitHub.
