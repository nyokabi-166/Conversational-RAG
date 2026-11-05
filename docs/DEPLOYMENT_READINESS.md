# Deployment Readiness and Operations

## Current deployment status

The supported setup in this repository is a local Docker Compose demonstration. GitHub Actions runs code checks and builds container images; the workflow does not deploy the application to a public host. The root Compose file uses local-development defaults, including a fallback PostgreSQL password, host-published service ports, and a browser API URL of `http://localhost:8000`. Do not expose this configuration directly to the public internet.

## What the current health endpoint tells us

`GET /` returns the API service name, environment, configured model provider, and model. It currently does not test the database, Chroma, or model-provider connectivity. A successful response therefore means only that the API process answered.

## Before a hosted demo

- Choose a host and confirm its cost, supported container workflow, persistent storage options, and region.
- Configure separate production secrets for database access, JWT signing, Auth0, LLM access, and any mail service. Keep them in the host's secret manager; never commit `.env` files or put provider credentials in `NEXT_PUBLIC_*` variables.
- Replace default passwords and restrict database/vector-store access to private networking. Publish only the web entry point and required API endpoint.
- Set the browser-facing API URL and Auth0 callback/logout URLs to the final HTTPS domain.
- Configure CORS to allow only the deployed frontend origin.
- Decide how PostgreSQL, Chroma's persistent index, and uploaded files will be backed up and restored. Test a restore before treating the service as recoverable.
- Ensure the uploaded policy corpus is loaded into the deployed vector store and record its source/version inventory.
- Add startup/readiness checks for PostgreSQL, Chroma, and the API; configure restart behavior and resource limits.
- Remove or disable experimental flight-provider endpoints that are not part of the supported user flow.
- Run the release checks and a browser smoke test against the hosted environment before presenting it as available.

## Operational monitoring to add

For an academic demo, begin with a small, reviewable set of signals:

1. **Availability:** external check of the frontend and a dependency-aware API readiness endpoint.
2. **Errors:** structured backend and frontend logs, with request IDs and no passwords, tokens, passenger questions containing personal data, or provider secrets.
3. **Dependencies:** database/Chroma connection failures, LLM provider errors, latency, and rate-limit responses.
4. **Capacity and cost:** memory/disk use, container restarts, model request counts, and provider spend or quota.
5. **Recovery:** backup timestamps and a recorded restore drill for persistent data.

These monitors are recommendations, not features already installed in the repository. A production deployment should include alerts and a named operator responsible for responding to them.

## Release checklist

- [ ] Deployment host and monthly cost documented.
- [ ] HTTPS and domain configured.
- [ ] Secrets stored in host-managed settings and rotated from local/demo values.
- [ ] CORS and Auth0 URLs limited to the deployed origins.
- [ ] PostgreSQL and vector data persistence/backups configured and restore tested.
- [ ] Policy corpus indexed and source inventory recorded.
- [ ] Health/readiness checks cover dependencies.
- [ ] Logs and alerts checked without exposing user secrets or private content.
- [ ] Passenger, staff, and administrator flows smoke-tested.
- [ ] Rollback image/version recorded.
- [ ] Public URL, release version, limitations, and operator documented.
