# Final evaluation runbook

All commands run from the repository root. The final run replaces
`backend/evaluation/results/`; the pilot is archived in
`analysis_extras/round5/pilot_eval/`.

Status (2026-11-17): the main 201-question run is complete in
`backend/evaluation/results/`. The 15-question post-hoc held-out check is complete
in `analysis_extras/final/heldout_results/`, with aggregates in
`analysis_extras/final/heldout_summary/`. Human review of the 6 unanswerable
rows, 50 validation rows, and 40 error-analysis rows is complete; the agreement
and Figures 6–8 have been generated. Thesis-ready corrections are in
`analysis_extras/final/thesis_updates.md`.

## Preconditions

1. DeepInfra credits topped up for the generation key and the judge key.
2. Working tree reviewed (`git status`); no secrets in output.
3. `backend/.env` contains `LLM_PROVIDER=deepinfra`, `DEEPINFRA_API_KEY`,
   `DEEPINFRA_JUDGE_API_KEY` (or the same key), and `EMBEDDING_PROVIDER=local`.
4. Tests pass: `backend\.venv\Scripts\python.exe -m pytest -q` (currently 96).

## Step 1 — Refresh vocabulary and freeze the guard

```powershell
backend\.venv\Scripts\python.exe backend\scripts\build_corpus_vocabulary.py
backend\.venv\Scripts\python.exe analysis_extras\round5\guard_validation.py
```

Expected: 157 chunks, 12 sources; 0 dev answerable false refusals; >=80% new
unanswerable refusal; 8/8 under-specified flagged. Do not retune on the 201
evaluation questions.

## Step 2 — Dry run (5 questions, no judge calls)

```powershell
backend\.venv\Scripts\python.exe backend\scripts\evaluate_rag.py --dry-run
```

Expected: about 8-10 generation calls. Check `backend/evaluation/results_dry_run/run_metadata.json`
(`status: dry_run_complete`), the projected full-run call count, and that refused
rows have no source links. No judge calls are made.

## Step 3 — Full fresh run

```powershell
backend\.venv\Scripts\python.exe backend\scripts\evaluate_rag.py
```

Expected generation calls: ~300-330. Judge calls are additional (at least 6 per
row; RAGAS may issue more). If the API returns HTTP 402, the script prints the
checkpoint path and exits; top up and re-run the same command to resume.

Outputs: `backend/evaluation/results/evaluation_report.csv`,
`run_metadata.json` (`status: completed`, end time, stage counts, hashes).

## Step 4 — Consistency check (15 questions x 3 runs, <=45 calls)

```powershell
backend\.venv\Scripts\python.exe analysis_extras\final\consistency_check.py
```

Output: `analysis_extras/final/consistency.json` (resumable after each run).

## Step 5 — Tables and figures

```powershell
backend\.venv\Scripts\python.exe analysis_extras\final\post_eval.py --consistency analysis_extras\final\consistency.json
backend\.venv\Scripts\python.exe analysis_extras\final\make_figures.py
```

Outputs in `analysis_extras/final/`: `overall_metrics.csv`, `paired_tests.csv`,
`category_metrics.csv`, `answerability_metrics.csv`, `refusal_summary.csv`,
`consistency_summary.csv`, `tables.md`, and 300-dpi PNG + SVG figures.

## Step 6 — Manual audit

- Read the 6 unanswerable rows and the Q180-Q201 band in `evaluation_report.csv`.
- Spot-check 10 randomly sampled answers against the cited context.
- Record residual risks (Q052, Q100, Q130 specifics; lexical guard limits;
  pilot invalidation) in the thesis limitations.
- Do not claim "0/201 citations": the stored response has citation markers
  stripped. Use the held-out citation-link observation only as a small-sample
  indicator.

## Step 7 - Post-hoc held-out check

Only run after every row in `analysis_extras/final/heldout_questions.csv` has
`review_status` set to `REVIEWED`.

```powershell
backend\.venv\Scripts\python.exe backend\scripts\evaluate_rag.py --dataset analysis_extras\final\heldout_questions.csv --output-dir analysis_extras\final\heldout_results
backend\.venv\Scripts\python.exe analysis_extras\final\post_eval.py --results-dir analysis_extras\final\heldout_results --out-dir analysis_extras\final\heldout_summary
```

The completed check used 165 DeepInfra calls (15 RAG generations, 15 baseline
generations, 135 judge calls) and took about 24 minutes. Treat the result as
exploratory. The unanswerable subset has n=3, and RAG refused 0/3 while producing
unsupported answers; do not use this check to claim general refusal safety. Only
1/15 answers returned source links.

## Step 8 - Human review and Figures 6-8 (complete)

Label these canonical files in order:

- `analysis_extras/unanswerable_review.csv`: fill `rag_type`, `baseline_type`,
  `safety` for 6 rows.
- `analysis_extras/validation_sample.csv`: fill `my_correct` for 50 rows while
  hiding the `ragas_*` columns.
- `analysis_extras/error_analysis_starter_DRAFT.csv`: fill
  `my_confirmed_cause` for 40 rows.

Run the label check before any agreement or figure output:

```powershell
backend\.venv\Scripts\python.exe analysis_extras\final\check_labels.py
```

After the check passes, compute agreement and regenerate the figures:

```powershell
backend\.venv\Scripts\python.exe analysis_extras\final\agreement.py
backend\.venv\Scripts\python.exe analysis_extras\final\make_figures.py
```

New outputs are `agreement_results.json`, `agreement_summary.csv`,
`unanswerable_summary.csv`, `error_cause_summary.csv`,
`fig_unanswerable_behaviour.*`, `fig_human_judge_agreement.*`, and
`fig_error_causes.*`. Figure 6 uses counts only because n=6. Figure 7 reports
human-versus-thresholded-RAGAS agreement, not inter-human agreement. Figure 8 is
omitted if the 40 error rows are not labelled.
