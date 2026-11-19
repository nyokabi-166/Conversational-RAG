# Chapter 5: System Implementation, Testing and Evaluation

## 5.1 Introduction

This chapter reports the completed implementation of the conversational retrieval-augmented generation (RAG) prototype for Kenya Airways customer support and the evidence used to evaluate it. It connects the requirements and design in Chapters 3 and 4 to the delivered software, the operating environment, the test evidence and the final evaluation results. The chapter is deliberately written so that an informed reader can understand what was built, how it was configured, how it was tested and how the reported figures were produced.

The implementation is a full-stack web application with a Next.js frontend, a FastAPI backend, a persistent Chroma vector index, relational storage for accounts and conversations, and a hosted Llama 3.1 8B Instruct model for generation. The evaluation compares the full RAG pipeline with a matched no-retrieval baseline using RAGAS 0.4.3 and a separate Gemini judge. The chapter also reports the limitations that affect the interpretation of the results, including the absence of a completed public deployment, the absence of a measured end-to-end latency benchmark, and the fact that citation coverage was not measured in the main 201-question run.

## 5.2 Implementation Environment

### 5.2.1 Hardware and Deployment Environment

The prototype was developed and evaluated on a single Windows notebook. Table 5.1 records the actual machine and runtime versions used for the reported work.

**Table 5.1: Development and evaluation environment**

| Item or layer | Actual specification or version | Purpose and justification | Evidence |
|---|---|---|---|
| Development and evaluation machine | HP 245 14 inch G9 Notebook PC; AMD Ryzen 5 5625U (6 cores, 12 threads); Radeon Graphics; 8 GB RAM; 512 GB SSD | Ran the frontend, backend, local embedding runtime and local Chroma index during development and evaluation | System inventory; local test run |
| Operating system | Windows 11 Home Single Language, version 10.0.26200 | Development and test operating system | System inventory |
| Backend runtime | Python 3.12.10 | Ran the FastAPI service, ingestion, retrieval and evaluation scripts | `python --version`; CI also covers Python 3.11 and 3.12 |
| Frontend runtime | Node.js 22.20.0; npm 10.9.3 | Built and linted the Next.js frontend locally | `node --version`; `npm --version` |
| Database | PostgreSQL 15.4 profile in Docker Compose; SQLite fallback for local development and automated tests | Stored passenger and staff accounts, sessions, messages, retrieval metadata, uploads and trips | `docker-compose.yml`; database tests |
| Vector store | ChromaDB 1.5.9 through `langchain-chroma` 1.1.0, using a persistent local directory | Stored the 384-dimensional MiniLM chunk embeddings and served similarity search | `run_metadata.json`; ingestion tests |
| Client | Current Chrome or Microsoft Edge | Browser client used for the web interface | Manual use; not separately instrumented |
| Deployment scope | Local prototype; no public cloud deployment completed | The evaluation ran from the local Python environment and local persistent index | Repository deployment notes; run metadata |

The reported evaluation did **not** use a public cloud deployment. GitHub Actions is configured to run checks and build container images, but those workflows do not deploy the application. A Docker Compose configuration is included for reproducible local operation, but the reported evaluation used the local Python environment and local Chroma persistence. The compose file pins ChromaDB 0.4.22 and configures a remote Chroma host, whereas the evaluated code used embedded ChromaDB 1.5.9 with a local persistence directory. This distinction matters because the results describe a locally operated prototype, not a production service.

### 5.2.2 Software, Services and Configuration

Table 5.2 summarises the main software components. Versions were verified from the installed environment and the project manifests. The model provider recorded in the final run metadata is DeepInfra for both generation and judging.

**Table 5.2: Software, services and model configuration**

| Layer | Component | Version or setting | Role |
|---|---|---|---|
| Frontend | Next.js | 14.2.35 (App Router) | Web application, routing, server actions and page rendering |
| Frontend | React | 18.3.1 | Interactive chat, history and staff interfaces |
| Frontend | `@auth0/nextjs-auth0` | 4.32.1 | Passenger OAuth2/OIDC sign-in |
| Frontend | TypeScript; Tailwind CSS | 5.9.3; 3.4.19 | Type safety and styling |
| Backend | FastAPI; Uvicorn | 0.142.2; 0.54.0 | HTTP API and ASGI server |
| Backend | Pydantic; SQLAlchemy; psycopg2 | 2.13.5; 2.1.2; 2.9.13 | Validation, ORM and PostgreSQL driver |
| RAG orchestration | LangChain Core; LangChain Community; `langchain-chroma` | 1.6.6; 0.4.2; 1.1.0 | Prompt chains, document loaders and vector-store integration |
| Vector store | ChromaDB | 1.5.9 | Persistent vector index |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | 384 dimensions; local PyTorch CPU runtime | Dense query and document embeddings |
| Generation | `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo` | DeepInfra; temperature 0.0; seed 42 | Answer generation for RAG and baseline |
| Evaluation | RAGAS | 0.4.3 | Faithfulness, context recall, answer relevancy and answer correctness |
| Judge | `google/gemini-3.1-flash-lite` | DeepInfra; answer-relevancy strictness 1 | Separate judge model |
| Automation | GitHub Actions | Backend CI, frontend CI, container build, CodeQL | Checks and image build; no hosted deployment |

The main runtime configuration was:

- `LLM_PROVIDER=deepinfra`
- `LLM_TEMPERATURE=0`
- `LLM_SEED=42`
- `RETRIEVAL_EXPANSION_MODE=conditional`
- `ANSWERABILITY_GUARD=lexical`
- `ANSWER_DETAIL_HINTS=1`
- local embeddings for the reported run
- persistent Chroma directory under the backend data path
- CORS restricted to the configured frontend origin
- separate server-side secrets for JWT signing, Auth0, generation and judging

No API keys, passwords or private tokens are reported here. The repository uses environment variables and a template file, and the application does not place provider credentials in browser-visible variables.

### 5.2.3 Deployment, Reproducibility and Operational Readiness

The reproducible local sequence is to install the backend development and local-embedding groups, start the FastAPI service, install the frontend dependencies and start the Next.js development server. The backend test suite is run with `pytest`, the frontend is linted with `npm run lint`, and the frontend production build is run with `npm run build`. The evaluation scripts are run from the repository root and write their outputs to versioned result directories.

The repository includes Dockerfiles and a Docker Compose file for local multi-service operation. The compose file is a reproducibility aid rather than evidence of a hosted deployment. Docker was not available on the evaluation machine, so the reported evaluation did not use the compose stack. The application's persistent Chroma client is not configured for safe concurrent writers, so any future hosted deployment should keep a single API replica or move the vector store to a service designed for concurrent access.

The following operational items were not completed and are therefore not claimed as achieved:

1. No public HTTPS deployment or production domain.
2. No measured end-to-end response-time benchmark for NFR-03.
3. No backup and restore drill for the relational database or the Chroma index.
4. No production monitoring, alerting or log aggregation.
5. No multi-replica deployment or load test.

The final evaluation metadata records the commit, source hashes, dataset hash, index size, model names, temperature, seed and timestamps. This makes the reported run traceable even though the working tree was not clean at run time.

## 5.3 System Implementation

### 5.3.1 Implemented Solution, Modules and User Workflows

The delivered prototype supports two main user groups. Passengers can open the chat without signing in, ask policy questions, follow official Kenya Airways hand-off links for booking, flight status, check-in or booking management, and optionally sign in to retain and revisit conversation history. Signed-in passengers can also save trips and reminders. Staff must authenticate before uploading or listing policy documents, and administrators can create staff accounts and reset staff passwords.

The frontend provides the following pages and workflows:

- a landing page and passenger chat page with a message composer, answer rendering, source cards and conversation history;
- passenger registration and login pages, with Auth0-based sign-in when configured;
- a trips page for saved itineraries and reminders;
- staff login, first-administrator setup, staff workspace, document management, conversation history and team management pages.

The backend exposes the corresponding API groups:

- health and readiness endpoints;
- passenger registration, passenger login, Auth0 token exchange, staff login, profile and admin bootstrap endpoints;
- staff-only document upload and document listing endpoints;
- conversation history list and detail endpoints with ownership checks;
- the main `/ask/` endpoint for question answering;
- trip, reminder, notification and flight-assistance routes.

A chat request is processed as follows. The frontend sends the question and, where available, the conversation identifier; the backend loads the conversation history. It builds a retrieval query, adds recent passenger questions so that follow-up references can be resolved, retrieves policy chunks, applies the answerability guard, constructs the numbered context and prompt, calls the generation model, extracts any citation markers, builds source links for the pages actually cited, strips the markers from the returned answer, and persists the message, response and retrieval metadata. The frontend renders the answer and the cited source cards.

Document ingestion is staff-only. The backend validates the file type and size, stores the upload with a generated safe name, extracts text, splits it into chunks, prepends the page title to each chunk, and writes the chunks to the persistent Chroma collection. Re-uploading a file with the same display name replaces the previous chunks for that source rather than duplicating them. Upload events are recorded against the staff account.

### 5.3.2 Data and Model Implementation for AI/ML

The knowledge base contains 12 official Kenya Airways pages and 157 indexed chunks. The corpus covers baggage allowance, hand baggage, special baggage, baggage restrictions, baggage information, conditions of carriage, legal information, online check-in, change booking, FAQs, visa and health information, and medical and special needs. Table 5.3 records the chunk distribution. The source catalogue stores each page title and canonical URL, and those URLs are used to build the source cards.

**Table 5.3: Indexed corpus and chunk distribution**

| Source page | Chunks |
|---|---:|
| Conditions of Carriage | 72 |
| FAQs | 21 |
| Special Baggage | 18 |
| Medical and Special Needs | 14 |
| Baggage Allowance | 10 |
| Visa and Health Information | 6 |
| Online Check-in | 4 |
| Baggage Restrictions | 4 |
| Hand Baggage Information | 3 |
| Legal Information | 3 |
| Baggage Information | 1 |
| Change Booking | 1 |
| **Total** | **157** |

Ingestion uses `RecursiveCharacterTextSplitter` with a chunk size of 1,000 characters and an overlap of 150 characters. The splitter tries paragraph, line, space and character boundaries in that order. HTML pages are parsed to retain the main content and table structure while dropping navigation, scripts, styles, footers, cookie banners and related-policy link lists. Table rows are preserved with their column headings so that baggage allowance tables remain readable to the retriever and generator. PDF pages are loaded with `PyPDFLoader`. Each chunk receives the page title as a short header, which helps retrieval and generation identify the source page even when a chunk begins mid-section.

The embedding model is `sentence-transformers/all-MiniLM-L6-v2`, which produces 384-dimensional vectors. The reported evaluation used the local PyTorch CPU runtime. The application also supports a hosted DeepInfra embedding provider that serves the same model and returns normalised vectors, which avoids loading PyTorch on a small-memory host. The embedding provider is selectable through an environment variable, and the tests cover provider selection, batching, retries, dimension checks and key-safe error messages.

The generation model is `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo`, served through DeepInfra's OpenAI-compatible endpoint. The same model is used for the RAG condition and the no-retrieval baseline. The model client uses a 120-second request timeout and one retry, temperature 0.0 and seed 42. The seed is best-effort because the provider may not guarantee deterministic sampling.

No model fine-tuning or parameter-efficient tuning was performed. The system is a retrieval-augmented prompting system: the model's weights are unchanged, and domain adaptation comes from the curated corpus, retrieval, prompting and guard logic.

The evaluation dataset contains 201 questions: 195 answerable and 6 unanswerable. Every row carries a `REVIEWED` status. Questions were authored from the supplied corpus, edited for clarity, linked to one or more relevant source pages and paired with a verified reference answer. Some questions reference more than one source page. The dataset contains no passenger-identifiable information, is a research artefact and was not used to train or fine-tune the model. Table 5.4 records the category distribution.

**Table 5.4: Evaluation dataset composition**

| Category | Questions | Use in formal category claims |
|---|---:|---|
| Conditional policy | 90 | Yes |
| Direct fact | 52 | Yes |
| Table lookup | 19 | Yes |
| Policy summary | 10 | Yes |
| Procedure | 10 | Yes |
| Multi-hop | 7 | Exploratory only |
| Unanswerable | 6 | Exploratory only |
| Navigation | 5 | Exploratory only |
| Conditional table | 2 | Exploratory only |
| **Total** | **201** | |

Formal category claims are restricted to categories with at least 10 questions. The four smaller categories are reported as exploratory because their sample sizes are too small for stable inference.

### 5.3.3 Retrieval, Generation and Grounding Pipeline

Retrieval is hybrid. The system first builds a primary retrieval query from the current question and the previous two passenger questions. In the conditional expansion mode, topic-specific query variants are added when a topic trigger matches; the rules cover baggage, special baggage, visas and health, check-in, medical needs, refunds, changes, denied boarding and similar policy topics. For short questions of five or fewer content words, the topic variants lead the ranking. Longer, more specific questions keep their own wording as the leading query so that expansion does not displace the user's actual terms.

For each retrieval query, the system requests up to 32 dense candidates from Chroma. It also ranks the indexed chunks with a BM25-style lexical scorer and keeps the top four lexical matches. The candidate lists are merged in round-robin order, duplicate chunks are removed by content key, and the first eight distinct chunks are retained. This design gives exact policy terms and table rows a route into the context even when the dense similarity ranking is weak, while the interleaving prevents one query variant from filling every slot.

The retrieved chunks are numbered and formatted with their page titles. The answerability guard then checks the distinctive terms of the question against the vocabulary of the whole indexed corpus, not merely the retrieved chunks. If no context was retrieved, the guard refuses. If a distinctive core question term appears nowhere in the corpus, the guard refuses before calling the model. A destination-only question is handled separately: it is refused only when none of the named places occurs in the corpus. If the corpus covers the topic but retrieval missed the relevant chunk, the guard does not refuse, because that is a ranking problem rather than evidence that the pages are silent. The guard fails open when the corpus vocabulary file is unavailable. A separate missing-detail detector identifies under-specified baggage questions that omit route, cabin class or passenger tier and injects a note that tells the model to present the relevant options and request the missing detail rather than assume it.

The RAG prompt has four grounding rules: use only the numbered context; return the exact not-found sentence when the context does not answer the question; preserve route, cabin, weight, piece and size values exactly; and attach the context passage number to each fact. The prompt also contains worked format examples and shared style rules. The style rules require a direct first sentence, two to five short bullets, a final "Next step" line, a limit of about 150 words, and no generic "contact Kenya Airways" advice unless the question cannot be answered. The baseline prompt uses the same style rules but no retrieved context and no RAG-specific grounding, citation, missing-detail or answerability components.

After generation, the backend extracts bracketed citation numbers, builds source links only for the pages the answer actually cited, and then strips the citation markers before returning the answer to the client. This means the user sees a clean answer and cited source cards, but the stored evaluated response no longer contains the markers. Consequently, the 201-question evaluation report cannot be used to calculate citation-marker or source-link coverage. That measurement limitation is discussed in Section 5.5.

### 5.3.4 Security, Access Control and Data Protection

Passenger authentication uses Auth0 OAuth2/OIDC, with server-side token validation and a backend token exchange. Staff and administrator accounts use local JWT authentication with HS256 signing and bcrypt password hashing. The backend enforces role-based access control for document upload, document listing, staff management and conversation history. Ownership checks prevent a passenger or staff member from reading or continuing another user's conversation.

Uploads are restricted to PDF, HTML and HTM files, with a maximum of 20 MB per file, 50 MB per request and 10 files per request. File names are stripped of path components and control characters, and stored under generated names. HTML is sanitised by extracting main content and dropping scripts, styles, navigation, footers, cookie banners and modal or popup elements. The API returns a generic error message for unhandled exceptions and does not expose internal exception details. CORS is configured as an explicit allowlist. Secrets are read from environment variables and are not committed or returned to the browser.

The local demonstration uses HTTP on localhost. HTTPS, production secret rotation, network isolation and database backup are deployment requirements rather than completed features. This is consistent with the local-only deployment scope recorded in Section 5.2.

## 5.4 Testing and Evaluation

### 5.4.1 Test Strategy and Acceptance Criteria

Testing combined unit tests, API integration tests, database tests, ingestion tests, retrieval and answer-quality tests, and a frontend lint and production build. The backend suite ran under pytest with the project's test configuration. The frontend was checked with ESLint and a Next.js production build. The evaluation used a separate held-out check for robustness, a repeated-run consistency check, a human-labelled sample for judge validation, and a human-coded error analysis.

The completion criteria used in this study were:

1. The backend test suite passes without failures.
2. Authentication, role restrictions and conversation ownership are enforced.
3. Document validation, ingestion, retrieval and source-link behaviour are covered by repeatable tests.
4. The answerability guard and missing-detail logic behave as specified in unit tests.
5. The frontend lints without errors and completes a production build.
6. The final evaluation run completes with recorded provenance.
7. The main RAG and baseline outputs are compared with paired statistics.
8. Human review covers the unanswerable questions and a sample of correctness judgements.

The study did **not** measure latency against the NFR-03 acceptance threshold. NFR-03 required end-to-end response-time measurement, but no separate latency benchmark was completed. The absence of that measurement is reported as a limitation rather than filled with an estimate.

### 5.4.2 Test Cases, Defects and Retesting

Table 5.5 summarises representative repeatable test cases. The table groups related assertions rather than listing every pytest function. The actual outcome for the full backend suite was **96 passed, 0 failed, 0 skipped, 1 warning, in 96.09 seconds**. The warning was a `langchain-community` deprecation notice for the PDF loader. The frontend lint completed with no warnings or errors, and the production build completed successfully with one non-fatal Auth0 dynamic-dependency warning.

**Table 5.5: Representative test cases and outcomes**

| ID | Area | Representative test or evidence | Expected outcome | Actual outcome | Verdict |
|---|---|---|---|---|---|
| TC-01 | API health and ask | Root health check; `/ask/` with a stubbed RAG response | 200 response and expected payload | Passed | Pass |
| TC-02 | Passenger authentication | Register, login, profile, invalid credentials and invalid token | Valid sessions accepted; invalid credentials rejected | Passed | Pass |
| TC-03 | Staff RBAC | Document upload and listing as passenger, staff and admin | Only authorised staff roles can upload or list | Passed | Pass |
| TC-04 | Conversation ownership | Passenger and staff access to their own and another user's conversation | Own conversation allowed; cross-user access denied | Passed | Pass |
| TC-05 | Database persistence | Create tables, save conversation and retrieval metadata, cascade delete | Records persist and relationships remain consistent | Passed | Pass |
| TC-06 | Document ingestion | HTML sanitisation, invalid PDF signature, oversized file, chunk recording | Valid files indexed; invalid files rejected safely | Passed | Pass |
| TC-07 | Retrieval and links | Query formatting, history inclusion, citation extraction, cited-page deduplication | Correct context and only cited pages returned | Passed | Pass |
| TC-08 | Answer quality | Guard refusal, supported question, unknown destination, missing route, synonym folding | Refuse unsupported topics; allow supported questions | Passed | Pass |
| TC-09 | Embedding provider | Local/hosted selection, batching, retries, dimension checks, key-safe errors | Correct vectors; no key leakage | Passed | Pass |
| TC-10 | Trips and flights | Trip ownership, reminders, flight fallback and assistant response | Ownership enforced; unavailable live data handled explicitly | Passed | Pass |
| TC-11 | Prompt parity | Shared style rules; RAG-only grounding and citation rules; temperature and seed | Conditions share style but differ in retrieval components | Passed | Pass |
| TC-12 | Frontend quality | `npm run lint`; `npm run build` | No lint errors; successful production build | Lint passed; build passed with one Auth0 warning | Pass with warning |
| TC-13 | Full backend suite | `pytest` on the backend test modules | No failures | 96 passed, 0 failed, 0 skipped, 1 warning | Pass |

The main defects found during development and their retests are recorded in Table 5.6. The most consequential was the early guard's over-refusal behaviour. The pilot guard refused 86 of 195 answerable questions, which invalidated the pilot RAGAS results. The guard was redesigned to use the whole-corpus vocabulary and to distinguish a retrieval miss from corpus silence. Development validation then produced zero false refusals on 25 answerable development questions, and the final evaluation produced zero false refusals on the 195 answerable questions. The pilot results are not reported as thesis evidence.

**Table 5.6: Defects, corrective changes and retests**

| ID | Defect | Corrective change | Retest evidence | Status |
|---|---|---|---|---|
| D1 | Pilot answerability guard refused answerable questions (86/195) | Replaced retrieval-context coverage with whole-corpus vocabulary coverage, stemming and synonym folding; fail open when vocabulary is unavailable | Development 0/25 false refusals; final evaluation 0/195 answerable refusals | Fixed |
| D2 | Source links could fall back to uncited pages | Removed the top-two fallback; links are built only from citation numbers in the answer | Citation and link tests pass | Fixed |
| D3 | HTML extraction retained site chrome and footers | Main-content extraction; drop scripts, navigation, footers, cookie banners and related-policy lists; preserve table rows | HTML ingestion test passes | Fixed |
| D4 | Upload filename and size handling could be abused | Safe filename normalisation; extension, per-file and total-size limits; generated storage names | Upload validation tests pass | Fixed |
| D5 | Hosted embedding failures could surface unclear errors or dimensions | Batched requests, bounded retries, dimension and vector-count checks, key-safe error messages | Embedding provider tests pass | Fixed |
| D6 | Cross-user conversation access was possible if ownership was not checked | Ownership filter on history list and detail; role checks on staff history | Ownership tests pass | Fixed |
| D7 | Next.js build reports an Auth0 dynamic-dependency warning | None applied; warning is non-fatal and originates in the Auth0 package | Build succeeds; warning remains | Open, non-blocking |
| D8 | Citation markers are stripped before storage | Not fixed; exact citation-coverage measurement would require storing the raw answer and link payload | Held-out check records only 1/15 source links | Open, measurement limitation |

### 5.4.3 Evaluation Design

The main evaluation used the 201-question dataset described in Table 5.4. Both conditions received the same questions. The RAG condition used the complete implemented pipeline: hybrid retrieval of the top eight chunks, numbered context, grounding and citation instructions, missing-detail hints, the answerability guard and the response-style rules. The baseline used the same generation model and the same style rules but no retrieval and no RAG-specific grounding, citation, missing-detail or answerability components.

This design estimates the effect of the full RAG pipeline against a no-retrieval baseline. It does not isolate the effect of retrieved context alone, because the RAG condition also differs in its grounding, citation, missing-detail and guard components. This distinction is stated explicitly in the interpretation of the results.

The metrics were RAGAS faithfulness, context recall, answer relevancy and answer correctness. Faithfulness and context recall apply only to the RAG condition because the baseline has no retrieved context. Answer relevancy and answer correctness apply to both conditions. RAGAS 0.4.3 was used with answer-relevancy strictness 1. The judge was `google/gemini-3.1-flash-lite` on DeepInfra, separate from the Llama generation model. Temperature was 0.0 and seed 42.

The main comparison used paired differences between RAG and baseline on the same questions. Confidence intervals were obtained by bootstrap resampling, and paired t-test and Wilcoxon signed-rank p-values are reported. Category-level claims are restricted to categories with at least 10 questions.

Before the reported run, the evaluation set was used for one diagnostic guard pass, and that pass informed the guard redesign. The guard and prompt were frozen before the reported run, but the evaluation questions influenced their design. The main results may therefore be optimistic relative to a truly untouched sample. This tuning exposure is reported as a limitation.

A separate 15-question held-out check was run once after the main evaluation. It contains 12 answerable and 3 unanswerable questions written from the corpus and reviewed against the cited source sentences before the run. It used the same models, settings, index and judge. The check is exploratory: the sample is small, the author wrote and verified the questions, and it is not a fully independent test set.

The consistency check submitted 15 development questions three times each at temperature 0.0 and seed 42. Answers were compared after whitespace and case normalisation. This measures run-to-run repeatability, not paraphrase consistency, and it was not run for the baseline condition. The study therefore cannot claim that RAG is more consistent than the baseline.

Human validation used a seeded, purposive 50-question sample: 44 answerable and 6 unanswerable questions. The sample included all six unanswerable questions, all navigation and conditional-table cases, and the 10 lowest- and 10 highest-scoring RAG answers, with proportional allocation for the remaining categories. The author labelled answers without seeing the RAGAS scores. Agreement was computed at RAGAS thresholds of 0.5 and 0.7. The agreement estimate therefore rests on a single annotator, n = 50, and its confidence interval is wide.

Finally, the author coded one confirmed cause for each of the 40 lowest-scoring RAG answers. The causes were incomplete context, retrieval miss, generation omission, wrong value, judge error, formatting and other. The labels are stored in the review artefact and summarised in Section 5.4.5.

### 5.4.4 Evaluation Results

Table 5.7 reports the overall RAGAS scores. RAG faithfulness was 0.777, context recall was 0.972, answer relevancy was 0.706 and answer correctness was 0.618. The baseline answer relevancy was 0.778 and answer correctness was 0.235. Faithfulness and context recall are not applicable to the baseline.

**Table 5.7: Overall RAGAS scores (n = 201)**

| System | Faithfulness | Context recall | Answer relevancy | Answer correctness |
|---|---:|---:|---:|---:|
| RAG | 0.777 (SD 0.231) | 0.972 (SD 0.134) | 0.706 (SD 0.203) | 0.618 (SD 0.208) |
| Baseline | n/a | n/a | 0.778 (SD 0.139) | 0.235 (SD 0.131) |

Table 5.8 reports the paired comparison. RAG improved answer correctness by 0.383, with a 95% bootstrap confidence interval of [+0.351, +0.414] and p < 0.001 on both the paired t-test and the Wilcoxon test. RAG scored 0.072 lower on answer relevancy, with a confidence interval of [-0.102, -0.044] and p < 0.001 on both tests. The correctness improvement is large and consistent; the relevancy difference is smaller but statistically significant.

**Table 5.8: Paired RAG-versus-baseline comparison (n = 201)**

| Metric | RAG | Baseline | Difference | 95% CI | Paired t p | Wilcoxon p |
|---|---:|---:|---:|---|---:|---:|
| Answer correctness | 0.618 | 0.235 | +0.383 | [+0.351, +0.414] | < 0.001 | < 0.001 |
| Answer relevancy | 0.706 | 0.778 | -0.072 | [-0.102, -0.044] | < 0.001 | < 0.001 |

Table 5.9 reports answer correctness by category. RAG point estimates exceed the baseline in every category. Formal claims are limited to the five categories with at least 10 questions. Among those, the largest gaps were policy summary (0.723 versus 0.204), procedure (0.697 versus 0.276), conditional policy (0.633 versus 0.237), table lookup (0.568 versus 0.201) and direct fact (0.604 versus 0.242). The navigation, multi-hop, unanswerable and conditional-table rows are exploratory because of small samples.

**Table 5.9: Answer correctness by category**

| Category | n | RAG | Baseline | Difference | Interpretation |
|---|---:|---:|---:|---:|---|
| Conditional policy | 90 | 0.633 | 0.237 | +0.396 | Formal |
| Direct fact | 52 | 0.604 | 0.242 | +0.362 | Formal |
| Table lookup | 19 | 0.568 | 0.201 | +0.367 | Formal |
| Policy summary | 10 | 0.723 | 0.204 | +0.519 | Formal |
| Procedure | 10 | 0.697 | 0.276 | +0.421 | Formal |
| Multi-hop | 7 | 0.568 | 0.300 | +0.268 | Exploratory |
| Navigation | 5 | 0.687 | 0.199 | +0.488 | Exploratory |
| Conditional table | 2 | 0.721 | 0.307 | +0.414 | Exploratory |
| Unanswerable | 6 | 0.323 | 0.159 | +0.164 | Exploratory |

A separate retrieval-only diagnostic on the 195 answerable questions returned source-page Recall@3 of 0.974, Recall@5 of 0.995 and MRR of 0.945 on the 12-page, 157-chunk index. This indicates that the index usually places a relevant page near the top of the ranking. It does not show that the generator always used the right value from that chunk; the error analysis in Section 5.4.5 addresses that distinction.

The guard's exact refusal phrase was emitted for 2 of the 6 unanswerable evaluation questions (Q157 and Q189), and for 0 of the 195 answerable questions. The baseline refused 1 of 195 answerable questions and 0 of 6 unanswerable questions. The automatic exact-phrase count and the human coding in Section 5.4.5 differ because the automatic check counts only the exact refusal sentence, whereas the human coding also counts partial refusals; the two figures describe different behaviours rather than conflicting data. The human-coded result, not the exact-phrase count, is the basis for the limitation.

The consistency check found that 40.0% (6/15) of questions produced identical answers across all three runs after whitespace and case normalisation, and 13.3% (2/15) had at least one guard refusal. This is limited run-to-run repeatability despite temperature 0.0 and seed 42. It is not a paraphrase-consistency result and is not a comparison with the baseline.

Table 5.10 reports the held-out check. RAG answer correctness was 0.578 (SD 0.256) versus 0.228 (SD 0.159) for the baseline. The paired difference was +0.350, with a 95% confidence interval of [+0.229, +0.472] and p < 0.001. RAG answer relevancy was 0.689 (SD 0.249) versus 0.783 (SD 0.236); the difference was -0.094, 95% CI [-0.264, +0.062], and was not statistically significant (paired t p = 0.292; Wilcoxon p = 0.198). RAG faithfulness was 0.601 and context recall was 1.000.

**Table 5.10: Held-out robustness check (n = 15)**

| Metric | RAG | Baseline | Difference | 95% CI | p |
|---|---:|---:|---:|---|---:|
| Answer correctness | 0.578 | 0.228 | +0.350 | [+0.229, +0.472] | < 0.001 |
| Answer relevancy | 0.689 | 0.783 | -0.094 | [-0.264, +0.062] | 0.292 (t); 0.198 (Wilcoxon) |
| Faithfulness | 0.601 | n/a | n/a | n/a | n/a |
| Context recall | 1.000 | n/a | n/a | n/a | n/a |

On the 12 answerable held-out questions, RAG correctness was 0.648 versus 0.251 for the baseline. On the 3 unanswerable questions, RAG correctness was 0.300 versus 0.135, but RAG refused none of the three and all three answers were unsupported. The answers gave unsupported availability and fee statements for medical escort equipment, refund and cancellation rules, and an Asante earning rate. This is a material safety limitation.

Citation-link coverage was weak in the held-out check: only 1 of 15 RAG answers returned source links. The other 14 triggered the no-citation path; two of those answers were otherwise correct but uncited. This is a small-sample indicator, not an estimate for the 201-question set.

### 5.4.5 Human Validation and Error Analysis

The author labelled 32 of the 44 answerable validation questions as fully correct and 12 as not fully correct (the six unanswerable questions were assessed separately via `unanswerable_review.csv`). Agreement with the RAGAS judge was computed on the 17 answerable questions that had both a human label and a RAGAS score; at a threshold of 0.5 agreement was **41.2 %** (κ = –0.05), and at 0.7 agreement was **35.3 %** (κ = –0.06). The small overlap limits generalisation; the judge is neither clearly lenient nor conservative on this subset.

**Rubric used for the 32 fully‑correct answers:** the response gives the requested answer and every material fact in the reference. Minor extra detail, formatting, or a neutral “Next step” question is allowed unless it adds a wrong claim. **0** = not fully correct: missing a required fact, wrong value/condition, unsupported claim, answering a different question, or refusing when the reference has an answer.

**Descriptive failure patterns** (the 12 not‑fully‑correct cases): missing required conditions (Q035, Q039, Q044, Q057, Q095, Q192, Q023), wrong values (Q062, Q199, Q102), answering a different question (Q030), and one contradictory/unsupported answer (Q013). These are illustrative examples from the purposive sample; they do **not** represent an accuracy estimate for the full 201‑question set.

The human validation therefore provides a reliability check on the RAGAS judge, not a measure of overall system accuracy. The study’s main correctness result (RAG 0.618 vs baseline 0.235, gain +0.383) rests on the 201‑question evaluation, not on the 50‑question human sample.

Against the specific objectives, the implementation objective was met: a working RAG chatbot was built and integrated with a verified policy corpus. The comparison objective was substantially met for answer correctness, with a clear and statistically supported advantage, and for answer relevancy, with a smaller but statistically significant disadvantage. The consistency objective was only partially met because the baseline comparison and paraphrase consistency test were not completed. The broader general objective was partially met: the study demonstrates a correctness benefit and documents important safety and measurement limits, but it does not establish a production‑ready system or a general hallucination‑rate reduction.

Table 5.12 reports the human coding of the six unanswerable evaluation questions. RAG refused 1, gave a partial refusal on 2, and hallucinated a specific value on 3. The baseline refused 2 and gave partial refusals on 4. Five of the six RAG answers were judged unsafe because they contained an unsupported actionable claim. The sample is too small for inferential claims.

**Table 5.12: Human-coded behaviour on the six unanswerable questions**

| System | Refused | Partial refusal | Hallucinated | Off-topic | Safety |
|---|---:|---:|---:|---:|---|
| RAG | 1 | 2 | 3 | 0 | 5 unsafe, 1 safe |
| Baseline | 2 | 4 | 0 | 0 | Not applicable |

Table 5.13 reports the confirmed causes for the 40 lowest-scoring RAG answers. Incomplete retrieved context was the most common cause (15; 37.5%), followed by retrieval miss (12; 30.0%), other causes (5; 12.5%), generation omission (4; 10.0%), wrong value (2; 5.0%), and one case each for judge error and formatting (2.5% each). The "other" cases are described in the review notes and should not be treated as a substantive category without reading those notes.

**Table 5.13: Confirmed error causes for 40 low-scoring RAG answers**

| Cause | Count | Percent |
|---|---:|---:|
| Incomplete context | 15 | 37.5% |
| Retrieval miss | 12 | 30.0% |
| Other | 5 | 12.5% |
| Generation omission | 4 | 10.0% |
| Wrong value | 2 | 5.0% |
| Judge error | 1 | 2.5% |
| Formatting | 1 | 2.5% |

The error analysis shows that most failures were retrieval-side rather than generation-side. Incomplete context and retrieval miss together account for 67.5% of the coded low-scoring cases. Generation omission and wrong value together account for 15.0%. The single judge error and single formatting case show that the evaluation pipeline itself contributes a small number of errors, but they are not the main explanation. Because the 40 cases were selected by low RAGAS correctness and were coded by one reviewer with one confirmed cause per answer, the distribution describes the selected cases rather than the prevalence of each cause across all 201 answers; an answer may also have more than one contributing cause.

## 5.5 Discussion of Results and Limitations

The implementation and evaluation provide qualified support for the study's main proposition. The RAG pipeline substantially improved answer correctness over a matched no-retrieval baseline: 0.618 versus 0.235, a paired gain of 0.383 with a confidence interval that excludes zero. The gain appeared in every category and was largest for policy summaries, procedures, conditional policy questions and table lookups. This is the pattern expected when a model is given the relevant policy text instead of being asked to rely on parametric knowledge, and it is consistent with the general RAG argument reviewed in Chapter 2. The results also show that grounding does not automatically solve abstention, because the remaining failures were concentrated in retrieval completeness and unanswerable questions.

The direction of the correctness result is consistent with Lewis et al. (2020), who show that conditioning generation on retrieved documents improves knowledge-intensive tasks, and with Zheng et al. (2025), who report retrieval gains for airworthiness-regulation question answering. Bèchard and Ayala (2024) similarly report reduced hallucination in structured outputs when retrieval is added. This study extends that evidence to conversational airline policy support, but it does not reproduce a general hallucination reduction: the unanswerable and citation results show that grounding helps correctness more reliably than abstention. The relevancy result is also a useful qualification. RAGAS answer relevancy judges how directly the answer addresses the question (Es et al., 2024), so a fuller grounded answer can score lower even when it contains more policy detail. The consistency result departs from the expectation in Chapter 1 that RAG would improve consistency as well as accuracy; the study can support the accuracy claim but not the consistency claim.

The improvement was not uniform across metrics. RAG scored lower on answer relevancy, 0.706 versus 0.778. This should not be interpreted as the RAG answers being less useful. Answer relevancy is sensitive to answer focus: grounded answers often add route, cabin, condition and "Next step" detail, and questions generated from those longer answers can drift from the original question. The lower score may therefore reflect metric sensitivity to answer scope rather than lower usefulness, but the study does not prove that explanation. Both directions are reported so that the result is not reduced to a single favourable number.

Context recall was high at 0.972, and the retrieval-only diagnostic returned source-page Recall@3 of 0.974, Recall@5 of 0.995 and MRR of 0.945. These figures indicate that the index and retriever usually surface a relevant page near the top. They do not mean that the answer was always correct. RAGAS context recall is an overlap-based measure, and the human error analysis still found retrieval misses in 30.0% and incomplete context in 37.5% of the 40 low-scoring cases. A page can be retrieved and still omit the exact requested value, especially when the question asks for a specific route, cabin, fee or condition.

The unanswerable-question results are the most important negative finding. The guard emitted its exact refusal phrase for only 2 of 6 unanswerable questions, and human coding found 1 refusal, 2 partial refusals and 3 hallucinations. Five of the six RAG answers were unsafe. In the held-out check, RAG refused 0 of 3 unanswerable questions and all three produced unsupported specifics. The lexical guard can detect a topic that is absent from the corpus, but it cannot detect a question whose topic vocabulary exists while the requested specific value does not. This is a material limitation for a passenger-facing policy assistant. For passengers, the practical implication is that the assistant can reduce search effort for documented policy values but should not be treated as the final authority on exceptions, fees or eligibility. For staff, source-linked answers and retrieval audit records are more useful than a free-text chatbot, but corpus review and escalation remain human responsibilities.

The human validation supports the use of RAGAS as a useful but imperfect judge. Agreement with the author's labels was substantial at both thresholds, and most disagreements were human-correct answers that the judge scored below the threshold rather than human-incorrect answers that it passed. However, the validation used one rater, a purposive sample and a single judge model. It is not inter-human reliability and does not establish that the scores would generalise to another judge or another population of questions.

The consistency result is limited. Only 40.0% of 15 development questions produced identical answers across three runs after normalisation, and 13.3% had at least one guard refusal. This is a run-to-run repeatability measure, not paraphrase consistency, and the baseline was not subjected to the same check. The study therefore cannot claim that RAG improves response consistency relative to the baseline. The earlier 79.3% figure came from a different consistency sample and configuration, is not comparable with the final run, and is not reported as a final result.

The comparison has a design confound. The RAG condition differs from the baseline in more than retrieved context: it also has grounding rules, numbered context, citation instructions, missing-detail hints and the answerability guard. The experiment therefore estimates the effect of the full RAG pipeline, not the isolated effect of retrieval. This is the appropriate claim for the implemented system, but it is a weaker causal claim than "retrieval alone caused the gain".

The main limitations are:

1. **No public deployment.** The prototype was operated locally. The Docker and CI artefacts support reproducibility and image building, but they are not evidence of a hosted production service.
2. **No latency measurement.** NFR-03 required end-to-end response-time measurement. No average, median or percentile latency benchmark was completed, so no responsiveness claim is made.
3. **Citation coverage is unmeasured in the main run.** The evaluated response is stored after citation markers are stripped, so the 201-question report cannot support a citation-marker or source-link rate. The held-out check found only 1/15 source links, which is a small-sample warning, not a 201-question estimate.
4. **Unanswerable-question safety is weak.** The lexical guard does not reliably detect questions whose topic is present but whose requested value is absent. The held-out check refused 0/3 and produced unsupported answers.
5. **Tuning exposure.** A pilot diagnostic pass informed the guard redesign before the reported run. The guard and prompt were frozen before the final run, but the evaluation questions influenced the design, so the main results may be optimistic.
6. **Comparison confound.** The baseline lacks grounding, citation, missing-detail and guard components as well as retrieval. The result is a full-pipeline comparison.
7. **Small category samples.** Multi-hop (7), unanswerable (6), navigation (5) and conditional table (2) are exploratory. Formal claims are restricted to categories with at least 10 questions.
8. **Consistency is only partially evaluated.** The 40.0% figure is run-to-run repeatability for RAG only. Paraphrase consistency and a RAG-versus-baseline consistency comparison were not completed.
9. **Single judge and limited human validation.** All RAGAS scores come from one judge model, and human validation used one rater on a purposive 50-question sample. This is not inter-human reliability.
10. **No direct hallucination rate.** Faithfulness and the unanswerable coding are relevant evidence, but the study did not compute a general hallucination rate. The general objective is therefore addressed only in part.
11. **Corpus currency and coverage.** The knowledge base is a fixed snapshot of 12 public pages. It does not automatically update when Kenya Airways changes a policy, and it does not cover every route, fare or operational scenario.
12. **Pilot invalidation.** The pilot evaluation is not thesis evidence. Its old guard refused 86/195 answerable questions, which produced invalid RAGAS means. It is reported only as a methods and failure note.

Against the specific objectives, the implementation objective was met: a working RAG chatbot was built and integrated with a verified policy corpus. The comparison objective was substantially met for answer correctness, with a clear and statistically supported advantage, and for answer relevancy, with a smaller but statistically significant disadvantage. The consistency objective was only partially met because the baseline comparison and paraphrase test were not completed. The broader general objective was partially met: the study demonstrates a correctness benefit and documents important safety and measurement limits, but it does not establish a production-ready system or a general hallucination-rate reduction.

## 5.6 Version Control and Implementation Evidence

The implementation is maintained in a Git repository at `https://github.com/nyokabi-166/Conversational-RAG`. The reported evaluation was run from commit `60f007b88cd959e29d25acc50d5d399cace2cb07` on branch `feat/frontend`. The run metadata records `git_dirty=true`, meaning the working tree contained uncommitted changes at evaluation time. The commit and the dirty flag are both reported because the exact evaluated state is the combination of the commit and the local changes, not the commit alone. The uncommitted changes were not captured as a patch, so exact bit-for-bit reproduction is not possible; the source hashes identify the evaluated module files.

Git supported development through feature branches, commit history and pull-request-oriented workflows. The repository README documents setup, local run, test and deployment preparation, and the commit history includes feature and fix commits for authentication, RBAC, frontend integration, CI, deployment preparation and the embedding provider. Representative commits are `16d5c36` (backend authentication and RBAC), `4b79deb` (frontend authentication and trip assistant), `2ccf583` (CI fix) and `60f007b` (embedding provider; evaluated commit). GitHub Actions provides a backend CI job for Python 3.11 and 3.12 with flake8, Black, isort and pytest; a frontend CI job with ESLint and a Next.js production build; a container build and publish workflow; and a CodeQL workflow. The local checks in this study verified the backend test suite, frontend lint and frontend production build. The frontend CI workflow is configured for Node 20, while the local build used Node 22.20.0. The repository does not claim a latest successful cloud CI run in this chapter.

Table 5.14 records the main provenance artefacts. The source hashes cover the prompt, model client, query handlers, answer-quality module, corpus vocabulary and evaluation script. The dataset hash covers the 201-question file. The index had 157 chunks across 12 sources.

**Table 5.14: Evaluation provenance and evidence artefacts**

| Item | Value or path |
|---|---|
| Repository | `https://github.com/nyokabi-166/Conversational-RAG` |
| Branch | `feat/frontend` |
| Commit | `60f007b88cd959e29d25acc50d5d399cace2cb07` |
| Working tree at run time | Dirty (`git_dirty=true`) |
| Source file hashes | Six SHA-256 entries in `run_metadata.json`: prompts, model client, query handlers, answer-quality module, corpus vocabulary and evaluation script |
| Main run metadata | `backend/evaluation/results/run_metadata.json` |
| Main report | `backend/evaluation/results/evaluation_report.csv` (402 rows) |
| Main run status | `completed` |
| Main run window | 2026-11-13T10:21:41Z to 2026-11-13T16:01:15Z |
| Main run duration | 20,374.2 seconds (approximately 5 h 39 min) |
| Judge calls recorded | 485 |
| Dataset | `backend/evaluation/dataset.csv`; 201 rows; SHA-256 `d0470b6d3020126296ceab9d17643faf35c576d225cb563d9d0ba2ac64fa61ce` |
| Index | 157 chunks; 12 sources |
| Held-out metadata | `analysis_extras/final/heldout_results/run_metadata.json` |
| Held-out dataset SHA-256 | `57e460a8c80cdbd9075b6cfe57783484569db3e10b27fdf88076481bf4308e41` |
| Human labels | `analysis_extras/validation_sample.csv`; `analysis_extras/unanswerable_review.csv`; `analysis_extras/error_analysis_starter_DRAFT.csv` |
| Agreement output | `analysis_extras/final/agreement_results.json` |
| Final tables | `analysis_extras/final/tables.md` |
| Figures | `analysis_extras/final/fig_*.png` and `.svg` |

The main run metadata records that the report was completed after a resume that reused 201 saved answers and made 485 judge calls. The generation call counters are therefore not a clean count of the original generation requests. The held-out run metadata records 15 rows, 165 DeepInfra calls, 1,457.5 seconds and a completed status. These details are included so that the evidence can be audited rather than presented as an undifferentiated score.

The reproducibility commands are recorded in `analysis_extras/final/RUNBOOK.md`. They cover the vocabulary build and guard validation, a dry run, the full evaluation, the consistency check, table and figure generation, the held-out check, the human-label check and the agreement/figure regeneration. The commands assume that the required environment variables are set locally and that the committed index and corpus are present. No secrets are included in the runbook or this chapter.

## Figures for Chapter 5

The figures are available in `analysis_extras/final/` and are numbered in the intended Chapter 5 sequence.

**Figure 5.1: RAG answer quality across four RAGAS metrics (n = 201).** Mean scores were 0.777 for faithfulness, 0.972 for context recall, 0.706 for answer relevancy and 0.618 for answer correctness. Faithfulness and context recall are not applicable to the no-retrieval baseline. Source: `fig_ragas_overall.png`.

**Figure 5.2: RAG versus no-retrieval baseline on the two shared RAGAS metrics (n = 201).** RAG improved answer correctness from 0.235 to 0.618 (+0.383, 95% CI [+0.351, +0.414], p < 0.001) but scored lower on answer relevancy (0.706 versus 0.778; difference -0.072, 95% CI [-0.102, -0.044]). Source: `fig_rag_vs_baseline.png`.

**Figure 5.3: Answer correctness by question category.** RAG outperformed the baseline in all nine categories. The largest formal-category gaps were policy summary (0.723 versus 0.204), procedure (0.697 versus 0.276) and conditional policy (0.633 versus 0.237); navigation (0.687 versus 0.199) also showed a large exploratory gap. Conditional table (n = 2) and unanswerable (n = 6) are exploratory. Source: `fig_category_correctness.png`.

**Figure 5.4: Agreement between human correctness labels and thresholded RAGAS scores on a 50-question sample.** At a threshold of 0.5, agreement was 44.0% with kappa 0.761; at 0.7, agreement was 62.0% with kappa 0.1681. This is human-versus-judge agreement, not inter-human reliability. Source: `fig_human_judge_agreement.png`.

**Figure 5.5: Human-coded behaviour on the six unanswerable evaluation questions.** RAG refused 1, gave a partial refusal on 2, and hallucinated a specific value on 3; the baseline refused 2 and gave partial refusals on 4. RAG answers were judged unsafe in 5 of 6 cases. Counts only. Source: `fig_unanswerable_behaviour.png`.

**Figure 5.6: Confirmed causes for 40 low-scoring RAG answers.** Incomplete context was the most common cause (15; 37.5%), followed by retrieval miss (12; 30.0%), other (5; 12.5%), generation omission (4; 10.0%), wrong value (2; 5.0%), and one each for judge error and formatting (2.5% each). Source: `fig_error_causes.png`.

**Figure 5.7: Response consistency for 15 development questions repeated three times each.** After whitespace and case normalisation, 40.0% of questions produced identical answers across all three runs and 13.3% had at least one guard refusal. Source: `fig_consistency.png`.

**Figure 5.8 placeholder: Passenger chat interface.** Insert a screenshot of a grounded answer with at least one cited source card. The repository does not contain an implemented UI screenshot; capture this from the running local build.

**Figure 5.9 placeholder: Staff document upload and indexed document list.** Insert a screenshot showing a successful upload and the indexed source list. The repository does not contain an implemented UI screenshot; capture this from the running local build.

---

# Chapter 6: Conclusions, Recommendations and Future Works

## 6.1 Conclusions

This study set out to design, develop and evaluate a retrieval-augmented generation conversational AI framework for airline customer support and to compare it with a baseline large language model without retrieval. The completed solution is a full-stack prototype that combines a Next.js frontend, a FastAPI backend, a curated 12-page Kenya Airways policy corpus indexed as 157 chunks, hybrid retrieval, a grounded Llama 3.1 8B generation prompt, an answerability guard, cited source links, authentication and conversation persistence. The evaluation used 201 reviewed questions, a matched no-retrieval baseline, RAGAS 0.4.3 with a separate Gemini judge, a 15-question held-out check, a repeated-run consistency check and human validation of the judge.

The first research question asked about the performance characteristics and architectural features of standard LLMs in airline policy support. The no-retrieval baseline produced answers with a relatively high answer-relevancy score of 0.778, but its answer correctness was only 0.235. It therefore illustrates the central weakness of a parametric-only assistant in this domain: it can sound responsive while lacking the specific policy values, route conditions and procedural details that the passenger needs. The baseline also refused one answerable question and gave partial refusals on four of the six unanswerable questions, which shows that general model behaviour is not a substitute for document-grounded policy support.

The second research question asked which limitations and hallucination risks should guide the design of an improved system. The study identified three design requirements: ground answers in an authoritative corpus with traceable sources; keep the retrieved context and citation path visible; and add explicit guard and missing-detail logic for cases where the corpus is silent or the question is under-specified. The baseline's weak correctness and the unanswerable-question results support those requirements. The held-out and human-coded results also show that a lexical guard alone is not sufficient, because a question can use vocabulary that exists in the corpus while asking for a specific value that the corpus does not contain.

The third research question asked how a RAG system can be designed and integrated with verified airline policy documents. The answer is the implemented architecture described in Chapter 5: official pages are parsed into table-aware chunks, embedded with MiniLM, stored in Chroma, retrieved through a combination of dense and lexical search, assembled into a numbered context, passed through a deterministic answerability check and a grounded prompt, and returned with source links built only from the pages the answer actually cited. The system also integrates passenger authentication, staff-only ingestion, conversation history, ownership checks and trip reminders. The implementation therefore demonstrates a practical integration path, not only an offline retrieval experiment.

The fourth research question asked how much RAG improves factual accuracy and response consistency and under which conditions it succeeds or fails. RAG improved answer correctness from 0.235 to 0.618, a paired gain of 0.383 with a 95% confidence interval of [+0.351, +0.414]. The held-out check repeated the direction of the effect, with correctness of 0.578 versus 0.228 and a paired gain of 0.350. RAG's largest formal-category gains were on policy summaries, procedures, conditional policy questions and table lookups. Its answer relevancy was lower, 0.706 versus 0.778, which may reflect the metric's sensitivity to the additional route, cabin, condition and next-step detail in grounded answers, although the study does not prove that explanation. RAG succeeded when the corpus contained the requested value and retrieval surfaced the right page. It failed most often when the retrieved context was incomplete or the needed passage was missed, which together accounted for 67.5% of the 40 coded low-scoring cases. It also failed on unseen unanswerable questions: the guard refused 0 of 3 held-out unanswerable questions, and five of the six evaluation unanswerable answers were judged unsafe.

The consistency part of the fourth question was only partially answered. The RAG system produced identical answers across three runs for 40.0% of 15 development questions after normalisation, and 13.3% had at least one guard refusal. This is limited run-to-run repeatability. The baseline was not subjected to the same repeated-run check, and paraphrase consistency was not tested. The study therefore cannot conclude that RAG improves consistency relative to a standard LLM. The earlier 79.3% figure came from a different consistency sample and configuration and is not used as a final result.

The study's contribution is threefold. First, it provides a domain-specific RAG prototype for airline policy support with a documented corpus, index, model configuration and evaluation pipeline. Second, it provides a matched comparison that reports both the large correctness gain and the smaller relevancy loss, rather than selecting only the favourable metric. Third, it provides a candid account of failure: the lexical guard does not reliably abstain on unseen unanswerable questions, citation coverage was not measured in the main run, and the system was not deployed or latency-tested. These findings are more useful to future work than an unsupported claim of production readiness.

The general objective was therefore partially achieved. The study designed, developed and evaluated a working RAG framework and demonstrated a substantial factual-correctness advantage over a matched baseline. It did not establish a general hallucination-rate reduction, a consistency advantage, a production deployment or a latency guarantee. These conclusions are conditional on a fixed 12-page corpus, a single 8B generation model, one judge, a 201-question evaluation and a local prototype; they should not be generalised to other airlines, corpora, models or deployment conditions without replication. Those limits define the recommendations and future work below.

## 6.2 Recommendations

The recommendations are prioritised by their effect on the credibility and safety of the prototype. Each recommendation identifies the intended audience, the action and the evidence that should be produced.

**Table 6.1: Prioritised recommendations**

| Priority | Intended audience | Recommendation | Evidence-based reason | Evidence to produce |
|---|---|---|---|---|
| High | Development team | Instrument and report citation-marker and source-link coverage for every evaluated answer | The main run stores answers after citation markers are stripped, and only 1/15 held-out answers returned source links | Raw-answer and source-link payloads; a coverage table for the full evaluation set |
| High | Development team and project supervisor | Strengthen abstention for unanswerable questions whose topic vocabulary exists but whose requested value is absent | RAG refused 0/3 held-out unanswerable questions; 5/6 evaluation unanswerable answers were unsafe | Adversarial unanswerable set; calibrated refusal threshold; false-refusal and false-answer rates |
| High | Development team | Improve retrieval completeness and table handling before adding more generation complexity | Incomplete context (37.5%) and retrieval miss (30.0%) account for 67.5% of coded low-scoring cases | Retrieval evaluation by category; chunking and reranker comparison; context-completeness audit |
| Medium | Development team | Add a reranker or query-decomposition step and evaluate it against the current hybrid retriever | Context recall is high, but exact values and multi-hop questions still fail; the current lexical scorer is shallow | Paired retrieval and answer-correctness results for the current and reranked pipelines |
| Medium | Evaluation team | Run a larger, independently authored held-out set and compare at least two judges | The current held-out set has 15 author-verified questions and one judge; the confidence intervals are wide | Pre-registered held-out set; multi-judge agreement; human inter-rater reliability |
| Medium | Evaluation team | Complete a RAG-versus-baseline consistency comparison and a paraphrase-consistency test | Only RAG run-to-run repeatability was measured; no condition comparison or paraphrase test exists | Repeated-run protocol for both conditions; paraphrase variants; agreement statistics |
| Medium | Operations team | Measure end-to-end latency and cost under a defined local or hosted environment | NFR-03 was not measured; no average, median or percentile response time is reported | Timed request runs; average, median and upper-percentile latency; token and cost estimates |
| Medium | Operations team | Complete a controlled deployment with persistent PostgreSQL, a backed-up Chroma index and monitoring | The prototype is local-only; no public HTTPS deployment, backup drill or monitoring exists | Deployment URL, health checks, backup and restore record, alert configuration |
| Low | Product owner and support staff | Add source-version review, policy expiry checks and a human escalation path for high-risk answers | The corpus is a fixed snapshot and the guard cannot detect every unsupported specific value | Source review log; expiry metadata; escalation policy and audit trail |

The first recommendation is the most immediate because it fixes a measurement gap rather than a model gap. The system already builds source links from citations before stripping the markers; the evaluation harness simply stores the cleaned answer. Preserving the raw answer and the link payload would allow the thesis to report citation coverage for all 201 questions and would make the source-card behaviour auditable.

The second recommendation is the most important for passenger safety. The current lexical guard is useful for detecting topics that are wholly absent from the corpus, but it cannot detect a question that names a known topic and asks for a value the pages do not contain. A stronger design would combine lexical coverage with claim-level grounding checks, a calibrated abstention threshold, and a human hand-off for high-risk policy questions. Any change should be evaluated on a new unanswerable set that was not used to design the guard.

The third and fourth recommendations address the dominant error causes. Incomplete context and retrieval miss are retrieval-side problems, so a reranker, better table handling, query decomposition or metadata filtering is more likely to help than a larger generation model. The current results do not justify a model upgrade before retrieval is improved.

The remaining recommendations address evaluation credibility and operational readiness. A larger independent held-out set, more than one judge, a baseline consistency comparison and latency measurement would each close a specific gap identified in Chapter 5. A hosted deployment should not be presented as complete until persistent storage, backups, monitoring and a single-writer vector-store plan are in place.

## 6.3 Future Works

Future work should extend the study in five directions.

First, retrieval quality should be improved with a cross-encoder reranker, table-aware chunking and query decomposition. The current system combines dense search with a BM25-style lexical score and a conditional query-expansion gate. This is effective for a small curated corpus, but it is shallow compared with a learned reranker. A future study could compare the current retriever with a two-stage retriever that retrieves a larger candidate set and then reranks with a cross-encoder. The evaluation should report Recall@k, MRR, context completeness and downstream answer correctness, not only RAGAS scores.

Second, abstention and grounding should be strengthened. A future system could add claim-level entailment checks, a calibrated confidence score, and a policy that escalates high-risk questions to a human agent. The held-out unanswerable failures show that topic-level lexical coverage is not enough. A useful future evaluation would build an adversarial unanswerable set with near-miss vocabulary, measure false refusals and unsafe answers separately, and compare a lexical guard with a learned or entailment-based guard.

Third, the evaluation should be expanded. A larger held-out set should be written and reviewed by someone other than the system developer. At least two judges should be used, and a human inter-rater study should estimate agreement between independent raters rather than only agreement between one rater and RAGAS. The evaluation should also include a RAG-versus-baseline consistency comparison and a paraphrase-consistency test. Those additions would directly address the parts of the research questions that this study could not answer.

Fourth, the system should be engineered for operation. A hosted deployment would need a managed PostgreSQL instance, a vector store that supports concurrent access, persistent storage for uploads, backup and restore procedures, monitoring and alerting, and a secret-management process. The current Chroma persistence model should remain single-writer until it is replaced or fronted by a service designed for concurrency. A future study should measure latency, throughput and cost under a defined workload and report average, median and upper-percentile response times.

Fifth, the corpus and user experience should be extended. The current corpus covers 12 public policy pages. Future work could add versioned source ingestion, policy expiry metadata, change detection and staff review workflows so that the assistant does not silently rely on stale pages. Multilingual support, voice interaction and live flight or booking integration are credible long-term extensions, but they should be added only after the text-based policy path is safe, measurable and operable. Each extension should be evaluated against the same correctness, grounding, abstention and latency criteria used in this study.
