# Addendum results: baseline repeatability and paraphrase pilot

Pilot checks on small samples. The 201-question results and the evaluated commit are unchanged.

## 1. Repeatability (15 dev questions, 3 runs each, same settings)

| System | Questions with identical text in all 3 runs |
|---|---|
| RAG | 6 of 15 (40.0%) |
| Baseline (no retrieval) | 1 of 15 (6.7%) |

Exact text match. Files: `consistency_baseline.json` (baseline), `../final/consistency.json` (RAG).

## 2. Paraphrase pilot (15 held-out questions, original + 2 rewordings, answer correctness)

| System | Original wording (n=15) | Reworded (n=30) | All (n=45) |
|---|---|---|---|
| RAG | 0.611 | 0.415 | 0.480 |
| Baseline | 0.246 | 0.239 | 0.241 |

- Spread of correctness across the 3 wordings of one question (mean range): RAG 0.358, baseline 0.183.
- RAG gave the "I couldn't find that" reply to 0 of 15 original questions and 9 of 30 reworded ones (8 were answerable questions). The baseline never refused.
- Reworded RAG answers that were not refused averaged 0.549 (n=21), close to 0.611 for the originals.
- Answerable questions only: RAG 0.690 (original) vs 0.446 (reworded); baseline 0.273 vs 0.258.

Reading: RAG stays above the baseline when questions are reworded, but its score drops mainly because it refuses reworded questions. The likely cause is the answerability check, which I have not confirmed from the logs.
Files: `paraphrase_dataset.csv`, `paraphrase_results/evaluation_report.csv`.
