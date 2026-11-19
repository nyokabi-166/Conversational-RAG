# Results snapshot (2026-11-19)

Frozen record of the final numbers, so they are not lost if other files change.
Sources: `backend/evaluation/results/evaluation_report.csv` (402 rows), `analysis_extras/final/*`.

## Setup
- Corpus: 12 official Kenya Airways pages, 157 chunks.
- Dataset: 201 questions (195 answerable, 6 unanswerable). Held-out check: 15 questions. Consistency check: 15 questions x 3 runs.
- Generator: Llama 3.1 8B Instruct Turbo on DeepInfra, temperature 0, seed 42. Judge: Gemini 3.1 Flash Lite, RAGAS 0.4.3.
- Evaluated commit 60f007b88cd959e29d25acc50d5d399cace2cb07 (working tree was dirty). Run 2026-11-13 10:21:41Z to 16:01:15Z, 485 judge calls.

## Main results
| Metric | RAG | Baseline |
|---|---|---|
| Answer correctness | 0.618 | 0.235 |
| Answer relevancy | 0.706 | 0.778 |
| Faithfulness | 0.777 | n/a |
| Context recall | 0.972 | n/a |

Correctness gain +0.383, 95% CI [+0.351, +0.414].

## Human validation (corrected 2026-11-19)
44 answerable answers labelled by the author: 32 fully correct, 12 not. 6 unanswerable rows are unlabelled here.
| Threshold | Agreement | Kappa | TP | TN | FP | FN |
|---|---|---|---|---|---|---|
| 0.5 | 84.1% | 0.609 | 28 | 9 | 3 | 4 |
| 0.7 | 72.7% | 0.455 | 21 | 11 | 1 | 11 |

The earlier figures (41.2% and 35.3%, kappa near zero, n = 17) came from the stale pilot sheet and are invalid.
The old files are kept as `review_backups/*_pilot_stale_2026-11-19.*`.

## Other checks
- Unanswerable (6): RAG 2 refused, 2 partial refusal, 2 hallucinated (2 unsafe, 4 safe). Baseline hallucinated all 6.
- Error causes, 40 lowest RAG scores overall: generation omission 27, wrong value 5, other 4, incomplete context 2, retrieval miss 1, judge error 1.
- Consistency: 40.0% of 15 questions gave identical answers across three runs.

## Hosting
Vercel (frontend), Render (backend), Neon (database), DeepInfra (LLM and hosted embeddings). The evaluation used local embeddings.
