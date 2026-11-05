# Backend RAG evaluation

The evaluation uses the backend's persisted Chroma collection and configured generation model. It sends each fixed question to both the RAG path and a no-retrieval baseline, then scores the results with an independent OpenRouter judge through RAGAS.

## Prepare the dataset

The repository includes a RAGAS-based draft generator. It uses the indexed Chroma chunks as source material and writes an AI-generated file marked `UNREVIEWED - AI generated`:

```powershell
poetry -C backend run python scripts/generate_eval_dataset.py --size 10
```

Read every question and reference answer against the named Kenya Airways source. Correct or remove anything unsupported. In `dataset.csv`, set `review_status` to exactly `reviewed` only after you have checked that row. The evaluator refuses to run if a CSV includes a `review_status` column with any other value. Other review metadata such as `source_file`, `source_url`, `category`, and `reviewer_notes` is retained for review but is not used as model input.

Alternatively, copy `dataset_template.csv` to `dataset.csv` and write the rows manually. Add one row per question:

- `question`: a realistic passenger question.
- `ground_truth`: the short, source-checked reference answer from the Kenya Airways documents.
- `review_status`: set to `reviewed` only after you personally check the answer against the cited source.

Do not put generated model responses or retrieved contexts in this file. The script collects those from the project at run time. Keep the question set fixed when comparing RAG and baseline.

## Configure evaluation

In `backend/.env`, set `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL` for generation. For the judge, set `OPENROUTER_JUDGE_API_KEY` to a key created under your separate OpenRouter account, and set `OPENROUTER_JUDGE_MODEL=google/gemini-3.1-flash-lite` (or another tested route). Add credits and usage limits to that judge account before running the evaluation. The judge key is separate from the generation key and must remain backend-only. Do not switch the generation or judge model partway through a formal evaluation; record both model IDs and providers. DeepInfra can be selected manually for generation by setting `LLM_PROVIDER=deepinfra` with `DEEPINFRA_API_KEY` and `DEEPINFRA_MODEL`. The optional draft generator uses `GEMINI_API_KEY` and `GEMINI_TESTSET_MODEL`. Manually review every draft against its source before adding questions to the fixed evaluation dataset.

Answer relevancy is configured with `strictness=1`, so RAGAS requests exactly one generated question per answer. This matches the selected OpenRouter judge route, which returned one completion when RAGAS requested three, and avoids silently scoring a different number of samples than configured. The trade-off is that answer relevancy has only one generated sample per answer; record this setting when reporting the metric. The evaluation CSV includes an `answer_relevancy_strictness` column.

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

## Visualize the scores

After a complete evaluation succeeds, create three paper-ready SVG figures and supporting CSV summaries:

```powershell
poetry -C backend run python scripts/visualize_evaluation.py
```

The files are saved in `backend/evaluation/results/`:

- `rag_vs_baseline.svg` shows the paired mean score difference (RAG minus baseline) for answer correctness and answer relevancy, with 95% bootstrap intervals.
- `rag_evidence_metrics.svg` shows the RAG faithfulness and context-recall distributions, with means and 95% bootstrap intervals.
- `category_correctness.svg` compares correctness by question category; categories with fewer than five questions are omitted from this figure.
- `paired_comparison.csv` contains the paired differences and interval bounds for the two shared metrics.
- `metric_summary.csv` contains each system's mean, standard deviation, bootstrap interval, and sample count.
- `category_summary.csv` contains category-level correctness means and intervals, including small categories omitted from the figure.

The resampling unit is the question (`case_id`), so RAG and baseline answers to the same question remain paired. Intervals summarize question-level variability in this reviewed dataset; they are not by themselves a significance test or proof of generalization. The report records `case_id` and category metadata so results can be traced to their reviewed questions. The visualizer rejects missing or invalid required scores and uses dataset metadata to label older reports, but final figures should come from the full evaluation.

The dataset template starts empty intentionally. Review every reference answer against its cited source before using scores as final project findings.
