# 🧠 RAG Backend Service

FastAPI backend service for airline customer support conversational AI, providing document ingestion, vector retrieval with ChromaDB, and generation through OpenRouter with a manually selectable DeepInfra backup.

## 🚀 Setup & Execution

```bash
# Install dependencies into virtualenv
poetry install --with dev

# Run locally
poetry run python -m src.main
```

## Language models

OpenRouter is the primary generation provider. Set `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL` in `backend/.env` for local runs. The checked-in example currently names `meta-llama/llama-3.3-70b-instruct`; verify the route and account access in OpenRouter before use. Inference may be billed or rate-limited according to the selected route.

### DeepInfra manual backup

DeepInfra is configured as a manual backup, not an automatic failover. To use it, set `LLM_PROVIDER=deepinfra` and configure `DEEPINFRA_API_KEY` and `DEEPINFRA_MODEL`, then restart the backend. Switch back by restoring `LLM_PROVIDER=openrouter`. The application does not silently switch providers or models. For a formal RAG-versus-baseline evaluation, keep one provider/model fixed for the entire run and record it; do not mix results from the backup model into the same comparison. Docker Compose reads settings from the project-root `.env`.

The same selected provider/model is used by chat, the RAG pipeline, and evaluation, while Gemini remains the separate RAGAS judge. Confirm the selected generation model matches the approved paper methodology before recording formal results.

HTML policy tables are indexed with their row and column labels preserved. Retrieval combines MiniLM semantic search with keyword ranking so exact policy terms and table rows can surface even when a broad question has weak semantic matches. After updating the parser, rebuild the existing local index once with `poetry -C backend run python scripts/reindex_documents.py` from the repository root. Re-uploading a document replaces its existing chunks for that filename instead of adding duplicate chunks.

The RAG chatbot and no-retrieval evaluation baseline use this same configured model. RAGAS uses Gemini Flash as a separate judge; set `GEMINI_API_KEY` and, if needed, `GEMINI_JUDGE_MODEL` in the same backend environment file.

## Passenger and staff accounts

Passengers create their own accounts at the frontend's passenger registration page. They sign in with their email at `/login`.

Staff do not have public registration. The first administrator is created from the frontend at `/staff/setup`; this page is available only when the backend has no `super_admin`. Before using it, set a random `ADMIN_SETUP_TOKEN` of at least 32 characters in the backend environment (for local development, `backend/.env`; for a deployment, the backend host's environment-variable settings). Enter that secret on the setup page, choose the admin username and password, and remove `ADMIN_SETUP_TOKEN` from the backend environment after setup. The admin is signed in automatically. If the initial demo administrator already exists but its password is unknown, the same protected page can reset that account's password when the token is temporarily configured; it cannot create a second administrator.

The administrator can create policy staff accounts from **Manage staff** in the staff workspace. Staff then sign in separately at `/staff/login`. There is no public staff sign-up. The API accepts staff credentials only at `/auth/staff/login` and passenger credentials only at `/auth/passenger/login`.

The backend enforces staff roles on document upload and listing regardless of what the frontend displays. The setup token is one-time: once an admin exists, the bootstrap endpoint refuses further use. Keep `JWT_SECRET_KEY` private and at least 32 characters long. The backend does not create demo staff accounts or other seed accounts on startup.

## Passenger flight tools

The passenger trip assistant can look up KQ status and KQ-filtered flight offers when provider credentials and suitable data access are configured. Set `AVIATIONSTACK_ACCESS_KEY` for status and `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET` for offers in the backend environment. Keep these credentials server-side; do not add them to frontend `NEXT_PUBLIC_` variables. `AMADEUS_API_URL` defaults to the test environment. Test-environment flight results are deliberately not presented as live availability. Use the production URL only after production credentials, terms, and permitted use are confirmed.

Without a configured or usable provider, the endpoints return an explicit unavailable state and a Kenya Airways hand-off link; they do not create sample flight results. Provider coverage for KQ must be verified before relying on the feature. Flight offers are for discovery only and must be rechecked on Kenya Airways; this app does not book, change, or cancel tickets.

Public read-only endpoints are `GET /flights/status?flight_number=KQ100&departure_date=YYYY-MM-DD` and `POST /flights/search`. `POST /flights/assistant` exposes bounded, read-only model tools for status and search. Passenger authentication is required for `/trips` and nested reminder endpoints. Saved trips contain itinerary details only; do not store PNRs, passport data, or payment details. The reminders are in-app reminders shown in the trip view, not email or push notifications.

The staff creation form lets the admin set the initial staff password, and the team page can reset a policy staff password. Share credentials privately with the staff member. A first-login password-change screen is not included yet.

## 🧪 Testing & Linting

```bash
poetry run pytest --cov=src tests/
poetry run flake8 .
poetry run black --check .
```
