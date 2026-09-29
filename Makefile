.PHONY: help install-all install-backend install-frontend format lint test docker-up docker-down clean

help:
	@echo "Available Monorepo Commands:"
	@echo "  make install-all      Install dependencies for both backend and frontend"
	@echo "  make install-backend  Install backend Poetry dependencies"
	@echo "  make install-frontend Install frontend npm dependencies"
	@echo "  make format           Format backend (Black, isort)"
	@echo "  make lint             Lint backend (Flake8) and frontend (ESLint)"
	@echo "  make test             Run backend pytest suite"
	@echo "  make docker-up        Spin up full-stack via Docker Compose"
	@echo "  make docker-down      Stop full-stack Docker Compose containers"
	@echo "  make clean            Remove cache and temporary build files"

install-all: install-backend install-frontend

install-backend:
	cd backend && poetry install --with dev

install-frontend:
	cd frontend && npm install

format:
	cd backend && poetry run black . && poetry run isort .

lint:
	cd backend && poetry run flake8 . && poetry run black --check .
	cd frontend && npm run lint

test:
	cd backend && poetry run pytest --cov=src --cov-report=term-missing tests/

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	rm -rf backend/.pytest_cache backend/.coverage backend/coverage.xml backend/htmlcov backend/.venv
	rm -rf frontend/.next frontend/node_modules
	find . -type d -name __pycache__ -exec rm -rf {} +
