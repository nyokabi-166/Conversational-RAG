# 🧠 RAG Backend Service

FastAPI backend service for airline customer support conversational AI, providing document ingestion, vector retrieval with ChromaDB, and generation through OpenRouter with a manually selectable DeepInfra backup.

## 🚀 Setup & Execution

```bash
# Install dependencies into virtualenv
poetry install --with dev

# Run locally
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Language models

OpenRouter is the primary generation provider. Set `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL` in `backend/.env` for local runs. The checked-in example currently names `meta-llama/llama-3.3-70b-instruct`; verify the route and account access in OpenRouter before use. Inference may be billed or rate-limited according to the selected route.

### DeepInfra manual backup

DeepInfra is configured as a manual backup, not an automatic failover. To use it, set `LLM_PROVIDER=deepinfra` and configure `DEEPINFRA_API_KEY` and `DEEPINFRA_MODEL`, then restart the backend. Switch back by restoring `LLM_PROVIDER=openrouter`. The application does not silently switch providers or models. For a formal RAG-versus-baseline evaluation, keep one provider/model fixed for the entire run and record it; do not mix results from the backup model into the same comparison. Docker Compose reads settings from the project-root `.env`.

The same selected provider/model is used by chat, the RAG pipeline, and the no-retrieval baseline. RAGAS uses a separate OpenRouter account for judging; set `OPENROUTER_JUDGE_API_KEY` and `OPENROUTER_JUDGE_MODEL` in `backend/.env`. The default judge route is `google/gemini-3.1-flash-lite`. Gemini remains available for draft evaluation-question generation through `GEMINI_API_KEY` and `GEMINI_TESTSET_MODEL`. Keep keys server-side, keep the generator and judge roles separate, and record both model names and providers when reporting results. Confirm the generation model matches the approved paper methodology before recording formal results.

HTML policy tables are indexed with their row and column labels preserved. Retrieval combines MiniLM semantic search with keyword ranking so exact policy terms and table rows can surface even when a broad question has weak semantic matches. After updating the parser, rebuild the existing local index once with `poetry -C backend run python scripts/reindex_documents.py` from the repository root. Re-uploading a document replaces its existing chunks for that filename instead of adding duplicate chunks.

The RAG chatbot and no-retrieval evaluation baseline use this same configured model. RAGAS uses a separate OpenRouter judge key; set `OPENROUTER_JUDGE_API_KEY` and `OPENROUTER_JUDGE_MODEL` in the backend environment file. Gemini is used only if you generate draft evaluation questions.

## Passenger and staff accounts

Passengers create their own accounts at the frontend's passenger registration page. They sign in with their email at `/login`.

Staff do not have public registration. The first administrator is created from the frontend at `/staff/setup`; this page is available only when the backend has no `super_admin`. Before using it, set a random `ADMIN_SETUP_TOKEN` of at least 32 characters in the backend environment (for local development, `backend/.env`; for a deployment, the backend host's environment-variable settings). Enter that secret on the setup page, choose the admin username and password, and remove `ADMIN_SETUP_TOKEN` from the backend environment after setup. The admin is signed in automatically. If the initial demo administrator already exists but its password is unknown, the same protected page can reset that account's password when the token is temporarily configured; it cannot create a second administrator.

The administrator can create policy staff accounts from **Manage staff** in the staff workspace. Staff then sign in separately at `/staff/login`. There is no public staff sign-up. The API accepts staff credentials only at `/auth/staff/login` and passenger credentials only at `/auth/passenger/login`.

The backend enforces staff roles on document upload and listing regardless of what the frontend displays. The setup token is one-time: once an admin exists, the bootstrap endpoint refuses further use. Keep `JWT_SECRET_KEY` private and at least 32 characters long. The backend does not create demo staff accounts or other seed accounts on startup.

## Passenger trip planning and Kenya Airways hand-off

The support chat handles policy questions and, when a passenger asks about booking, flight status, check-in, or managing a booking, provides a direct link to the relevant official Kenya Airways page. It does not query live flight providers, display fares or schedules, or create or change bookings. For an unclear flight-help request, it asks which action the passenger needs before sharing the relevant link. Do not ask passengers to share booking references, passport data, or payment details in chat.

Signed-in passengers can save itinerary details and create reminders under **My trips**. These reminders do not check live flight status. The older experimental flight-provider endpoints and Aviationstack/Amadeus adapters remain in the backend source but are not called by the current frontend. Do not configure provider credentials or treat those endpoints as part of the current supported user flow. Remove or secure those routes before a public deployment if the decision to exclude provider access is permanent.

The staff creation form lets the admin set the initial staff password, and the team page can reset a policy staff password. Share credentials privately with the staff member. A first-login password-change screen is not included yet.

## 🧪 Testing & Linting

```bash
poetry run pytest --cov=src tests/
poetry run flake8 .
poetry run black --check .
```
