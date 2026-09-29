.PHONY: help install format lint test docker-build docker-run clean

help:
	@echo "Available commands:"
	@echo "  make install       Install dependencies using Poetry"
	@echo "  make format        Format code using Black and isort"
	@echo "  make lint          Check code with flake8, black, and isort"
	@echo "  make test          Run pytest suite with coverage"
	@echo "  make docker-build  Build production Docker image"
	@echo "  make docker-run    Run production container locally"
	@echo "  make clean         Remove cache and temporary files"

install:
	poetry install --with dev

format:
	poetry run black .
	poetry run isort .

lint:
	poetry run flake8 .
	poetry run black --check .
	poetry run isort --check-only .

test:
	poetry run pytest --cov=src --cov-report=term-missing tests/

docker-build:
	docker build -t rag-project:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env rag-project:latest

clean:
	rm -rf .pytest_cache .coverage coverage.xml htmlcov .venv dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
