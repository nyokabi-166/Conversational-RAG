# Azure deployment plan

**Status: preparation only.** No Azure resources have been created. Do not treat the
GitHub container build as a live deployment.

## Target architecture

| Component | Azure deployment | Notes |
| --- | --- | --- |
| Next.js web app | Azure Container Apps, external HTTPS ingress | Uses the existing standalone Next.js Docker image. The public API URL is a build-time `NEXT_PUBLIC_API_URL`, so build the frontend image after the API URL is known. |
| FastAPI API | Azure Container Apps, external HTTPS ingress | Runs Uvicorn, uses explicit CORS origins, and exposes liveness/readiness endpoints. Keep maximum replicas at one while Chroma uses its local SQLite-backed store. |
| Accounts, chat history, trips | Azure Database for PostgreSQL Flexible Server | Durable managed database; configure private VNet access so it has no public database endpoint. Provision only after checking the student subscription's remaining credit and the selected server's cost. |
| Uploaded policies and Chroma index | Azure Files share mounted into the API container | Mount persistent paths for both `CHROMA_PERSIST_DIRECTORY` and `UPLOAD_DIRECTORY`. Keep the API at one replica: the current Chroma persistence model is not configured for safe concurrent replicas. Back up this share before reindexing or changing embedding models. |
| Text generation | OpenRouter, called by the backend | `OPENROUTER_API_KEY` stays in Container Apps secrets. LLM use is billed/limited by OpenRouter separately from Azure. |
| Login | Auth0 | Auth0 secrets are server-side frontend settings; the browser receives only the API base URL. Update Auth0 callback, logout, and allowed web origins after the frontend URL exists. |

Container Apps Consumption can scale replicas to zero and has monthly free usage grants,
but supporting storage and database services can still cost money. For private database
access, the Container Apps environment and PostgreSQL server need compatible VNet/subnet
and DNS setup; select this network design before creating either resource because the
network type cannot be switched later. Azure supports custom-VNet integration for
workload-profile Container Apps environments and private VNet integration for PostgreSQL.
Sources: [Container Apps custom VNet](https://learn.microsoft.com/en-us/azure/container-apps/custom-virtual-networks), [PostgreSQL private networking](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-networking-private).
Azure budgets send
alerts; they do not automatically stop resources. Azure for Students currently advertises
$100 credit for 12 months, subject to eligibility and offer terms. Check your subscription
and each region's estimate before deployment. Sources: [Container Apps billing](https://learn.microsoft.com/en-us/azure/container-apps/billing), [Azure for Students](https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0170p), [Azure budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets).

## Deployment blockers and safeguards

- [ ] Sign in to an active Azure subscription and record its offer type and remaining credit. Azure CLI and Docker are not currently available in the local environment.
- [ ] Confirm the region offers Container Apps and PostgreSQL Flexible Server, then review the monthly estimate for PostgreSQL, Azure Files, logs, and any registry/storage resources.
- [ ] Set a resource-group budget and alerts before provisioning. Alerts are notifications, not spending caps. Do not enable pay-as-you-go or add payment details just to get around exhausted student credit.
- [ ] Choose whether to use Azure Container Registry or the existing GitHub Container Registry images. Confirm registry visibility/access before relying on GHCR from Azure.
- [ ] Set up durable PostgreSQL and Azure Files before the first deployment. Do not deploy the current local SQLite/Chroma layout on ephemeral container storage.
- [ ] Use a unique production `JWT_SECRET_KEY`, backend-only provider secrets, and Auth0 production values. Never place OpenRouter, database, JWT, or Auth0 client secrets in `NEXT_PUBLIC_*` variables or the repository.
- [ ] Set `CORS_ORIGINS` to the exact deployed web origin. Do not use wildcard origins with credentials.
- [ ] Keep the backend at one replica until the vector store is moved to a service designed for concurrent access. The reminder worker runs inside the API and is not reliable while the app scales to zero.
- [ ] Use the API's `/health/live` and `/health/ready` endpoints for platform checks. Readiness checks PostgreSQL only and deliberately makes no model-provider call.
- [ ] Before changing the live version, deploy a staging revision and verify sign-in, chat, citations, passenger history, staff-only document upload, uploaded-document persistence after restart, trip flows, and safe behavior during provider outage.
- [ ] Record the app URLs, code commit, model route, subscription/credit status, and demo limitations. Keep local Docker Compose as the rollback/demo fallback.

## Deployment sequence

1. In Azure Portal, open the active subscription and verify the offer/credit balance. Create a small monthly budget with notification thresholds. Review likely PostgreSQL and storage costs; stop here if they exceed the available credit.
2. Create a dedicated resource group in a supported region and a VNet with separate delegated subnets for Container Apps and PostgreSQL. Create the PostgreSQL private DNS zone and link it to the VNet. Create PostgreSQL Flexible Server with private VNet access and a strong unique password; it must have no public database endpoint.
3. Create an Azure Container Apps environment using a workload-profile environment integrated with the VNet. Create the storage account and Azure Files share for Chroma and uploads. Then create the API container app with external HTTP ingress, HTTPS only, min replicas 0 and max replicas 1, and target port 8000. Set `/health/live` as liveness and `/health/ready` as readiness/startup check.
4. Configure API environment values: `APP_ENV=production`, `CORS_ORIGINS=<frontend-origin>`, `DATABASE_URL=<PostgreSQL connection string>`, `CHROMA_PERSIST_DIRECTORY=/mnt/policy/chroma_db`, `UPLOAD_DIRECTORY=/mnt/policy/uploads`, and the model/auth values required by the selected backend flows. Add credentials through Container Apps secrets (or Key Vault), never as source-controlled config.
5. Attach the Azure Files share to the API app at `/mnt/policy`; verify write access for the container's non-root `appuser`. Keep one API replica because local Chroma is SQLite-backed.
6. Create the frontend container app with external HTTPS ingress and the matching port 3000. Build its image with `NEXT_PUBLIC_API_URL=https://<api-fqdn>`. Set Auth0 server-side configuration in the frontend Container App secrets/settings.
7. Add the frontend URL to Auth0's callback/logout/web-origin allowlists and set the API's `CORS_ORIGINS` to the frontend origin. Confirm all API and authentication URLs use HTTPS.
8. Upload a small verified Kenya Airways policy corpus via the staff account. Restart the API and confirm the same sources remain searchable. Run a focused manual end-to-end check from a clean browser; record results and limitations.
9. Only after manual staging succeeds, configure GitHub Actions deployment with short-lived federated credentials (OIDC) and least-privilege access. Keep build/publish separate from deployment and deploy immutable commit tags.

## Changes prepared in this repository

- The backend image starts Uvicorn and honors the host-provided port.
- The API's CORS allowlist is configured with `CORS_ORIGINS` and its unhandled-error response does not return internal exception details.
- Liveness and database-readiness endpoints are available at `/health/live` and `/health/ready`.
- Chroma and upload paths can be pointed at a mounted persistent directory.
- The frontend image accepts its public API URL as a Docker build argument.

These are preparation changes only. This environment has no Azure CLI, Docker, or active
Azure sign-in, so no cloud resource creation or deployment has been performed. The
current code also initializes database tables at startup rather than running a managed
migration release; introduce and test a repeatable migration step before treating this
as a production service.
