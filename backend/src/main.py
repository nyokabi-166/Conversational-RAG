"""Main entry point for RAG backend service."""

import os
from typing import Dict


def get_application_status() -> Dict[str, str]:
    """Return health and environment status."""
    env = os.getenv("APP_ENV", "development")
    return {
        "status": "healthy",
        "environment": env,
        "service": "rag-backend",
    }


def main() -> None:
    """Run local service."""
    status = get_application_status()
    print(f"Starting RAG Backend: {status}")


if __name__ == "__main__":
    main()
