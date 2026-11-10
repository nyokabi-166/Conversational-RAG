# Deploying the backend to Hugging Face Spaces + Neon

The frontend stays on Vercel. Only the API moves.

## 1. Neon (database)
1. Create a Neon project and a database.
2. Copy the connection string. Use the **pooled** one and keep `?sslmode=require`
   (a `channel_binding=require` suffix is fine; the image uses libpq 17).
3. The tables are created automatically on first start (`init_db()`), so the
   database can be empty. It starts empty: see step 7.

## 2. Hugging Face Space
1. New Space -> SDK **Docker** -> Blank -> **CPU basic** (free) -> **Public**.
   Space name example: `airline-rag-api`.
2. Settings -> Access Tokens -> create a token with **Write** permission.
3. Space URL becomes `https://<username>-<space-name>.hf.space`
   (lower-case; underscores turn into hyphens).

## 3. Space settings -> Variables and secrets
Copy the values from the Render environment (do not paste them into git).

Secrets:
- `DATABASE_URL` (the Neon string)
- `DEEPINFRA_API_KEY`
- `JWT_SECRET_KEY`
- `ADMIN_SETUP_TOKEN`
- `RESEND_API_KEY`, `SMTP_PASSWORD` (only if you use them)
- `AMADEUS_CLIENT_SECRET`, `AVIATIONSTACK_ACCESS_KEY` (only if you use them)

Variables:
- `LLM_PROVIDER=deepinfra`
- `DEEPINFRA_MODEL` (same as on Render)
- `APP_ENV` (same as on Render)
- `AUTH0_DOMAIN` (same as on Render)
- `CORS_ORIGINS=https://conversational-rag-sandy.vercel.app`
- `CHROMA_PERSIST_DIRECTORY=./data/chroma_db`
- `EMAIL_FROM`, `AMADEUS_CLIENT_ID`, `AMADEUS_API_URL` (only if you use them)

Do NOT set `PORT`; the image already uses 7860.

## 4. Push the code
```powershell
$env:HF_TOKEN = "hf_..."     # the write token
.\deploy\huggingface\deploy.ps1 -SpaceId "<username>/<space-name>"
```
Watch the build under the Space's **Logs** tab. The first build is slow
(PyTorch CPU + model download), roughly 10-20 minutes.

## 5. Test
- `https://<username>-<space-name>.hf.space/health/ready` -> `{"status":"ready"}`
- Ask a baggage question; `sources` should be non-empty.

## 6. Point the frontend at it
Vercel -> Project -> Settings -> Environment Variables:
`NEXT_PUBLIC_API_URL=https://<username>-<space-name>.hf.space`
Then **redeploy** (the value is baked in at build time).

## 7. Things that change
- The Neon database starts empty. Create the first staff account again with
  the setup token. Passengers must register again (Auth0 users are separate).
- Documents uploaded through the staff UI live on the Space's disk and are
  lost when the Space restarts or is redeployed. The baked-in index
  (`backend/kb_index`) is restored every time. To make an upload permanent,
  re-index locally, refresh `backend/kb_index`, and run deploy.ps1 again.
- Free Spaces go to sleep after a period of inactivity and wake on the next
  request (the first request after sleeping is slow).
- Keep `kb_index` and Render in step if you still run Render in parallel.
