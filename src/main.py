"""Main entry point for the RAG project application."""

import os
from typing import Dict


def get_application_status() -> Dict[str, str]:
    """Return basic health and environment status."""
    env = os.getenv("APP_ENV", "development")
    return {
        "status": "healthy",
        "environment": env,
        "service": "rag-project",
    }


def main() -> None:
    """Run entrypoint for local execution."""
    status = get_application_status()
    print(f"Starting RAG application: {status}")


if __name__ == "__main__":
    main()
