# Build-Phase Evidence Register

Use this file to connect requirements to implementation and evidence. Fill in actual commit IDs, run links, evaluation results, and screenshots as they become available. Do not mark an item complete based only on code being present.

| Build-phase expectation | Project evidence to retain | Status |
|---|---|---|
| Reproducible development setup | Root README, backend README, environment templates, Docker Compose setup | Implemented for local development; verify from a clean checkout |
| Version control and automation | Git history, pull requests, CI workflow, CodeQL, container build workflow | Workflows exist; attach the latest successful run and release commit |
| End-to-end core workflow | Browser demo: policy upload → retrieval → cited answer; passenger login/history; staff authorization | Implemented; capture a dated smoke-test record |
| Failure and access checks | Backend test report and CI run showing invalid input, anonymous/wrong-role access, and ownership cases | Tests exist; attach latest passing CI evidence, including changes still under verification |
| Reviewed evaluation set | Versioned dataset, source inventory, reviewer status, fixed model/judge configuration | In progress: questions are drafts pending manual source review |
| Initial evaluation and baseline | Saved RAG and no-retrieval output, metrics, model IDs, judge, commit, and brief error analysis | Not complete until the reviewed set is evaluated and results are retained |
| Design and requirement traceability | Architecture diagram, requirement-to-component/test/evidence table, documented limits | Needs final report-ready artifacts |
| Hosted release and operations | HTTPS URL, deployment configuration, health checks, monitoring, backup/restore evidence, rollback version | Not complete; current workflow builds images but does not deploy |
| User and operator handover | User guide, deployment/operator runbook, known limitations, demo steps | Draft guides added; verify against the final application and deployment |
| Final report and presentation | Updated chapters, diagrams, screenshots, evaluation tables, limitations, demo backup | Not evidenced in this repository yet; add after evaluation and deployment decisions |

## Evidence record for each test or evaluation

For each run, record:

- Date and time (Africa/Nairobi)
- Git commit or release tag
- Environment (local/hosted), OS, and runtime versions
- Command or user flow tested
- Dataset/corpus version and source URLs where relevant
- Model provider/model and judge model, without recording API keys
- Result, failures, and follow-up action
- Link or path to the saved report, screenshot, or CI run
