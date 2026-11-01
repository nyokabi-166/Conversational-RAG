# Backend RAG evaluation

The evaluation uses the backend's persisted Chroma collection and configured generation model. It sends each fixed question to both the RAG path and a no-retrieval baseline, then scores the results with Gemini through RAGAS.

## Prepare the dataset

The repository includes a RAGAS-based draft generator. It uses the indexed Chroma chunks as source material and writes an AI-generated file marked `UNREVIEWED - AI generated`:

```powershell
poetry -C backend run python scripts/generate_eval_dataset.py --size 10
```

Read every question and reference answer against the Kenya Airways source context. Delete or correct anything unsupported, then copy the reviewed `question` and `ground_truth` columns into `dataset.csv`. The evaluator ignores the extra `source_contexts` and `review_status` columns, so you can keep them in the CSV while reviewing.

Alternatively, copy `dataset_template.csv` to `dataset.csv` and write the rows manually. Add one row per question:

- `question`: a realistic passenger question.
- `ground_truth`: the short, source-checked reference answer from the Kenya Airways documents.

Do not put generated model responses or retrieved contexts in this file. The script collects those from the project at run time. Keep the question set fixed when comparing RAG and baseline.

## Configure evaluation

In `backend/.env`, set `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL` for generation, and `GEMINI_API_KEY` and `GEMINI_JUDGE_MODEL` for the independent RAGAS judge. OpenRouter's selected route may have usage charges or rate limits. DeepInfra can be selected manually by setting `LLM_PROVIDER=deepinfra` with `DEEPINFRA_API_KEY` and `DEEPINFRA_MODEL`; do not switch providers partway through a formal evaluation. Keep the provider and exact model fixed for both RAG and no-retrieval baseline runs, and record their identifiers with each result. The draft generator uses `GEMINI_TESTSET_MODEL` (default `gemini-3.8-flash`). If the same Gemini model drafts questions and judges answers, disclose that in the methodology; manually review every draft against its source before adding questions to the fixed evaluation dataset.

Install the evaluation-only packages once, from the repository root. This adds them to the backend's Poetry dependency group and updates its lock file:

```powershell
poetry -C backend add --group evaluation ragas google-genai datasets
```

This is an install command, not a separate RAGAS script to download. The backend already provides LangChain and the MiniLM embeddings used by both scripts.

## Run

Run from the repository root. Poetry runs the script with the backend project directory as its working directory, so use this path:

```powershell
poetry -C backend run python scripts/evaluate_rag.py --limit 5
```

Remove `--limit 5` to evaluate every row. Results are written to `backend/evaluation/results/evaluation_report.csv`.

Faithfulness and context recall are reported for RAG, where retrieved evidence exists. The baseline is scored for answer relevancy and answer correctness; context recall is not meaningful when retrieval is deliberately absent.

The dataset template starts empty intentionally. Review every reference answer against its cited source before using scores as final project findings.
