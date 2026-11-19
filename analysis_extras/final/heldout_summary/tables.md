# Final evaluation summary

## Overall RAGAS scores

| System | Metric | Mean | SD | n |
|---|---|---:|---:|---:|
| Baseline | answer_relevancy | 0.783 | 0.236 | 15 |
| Baseline | answer_correctness | 0.228 | 0.159 | 15 |
| RAG | faithfulness | 0.601 | 0.310 | 15 |
| RAG | context_recall | 1.000 | 0.000 | 15 |
| RAG | answer_relevancy | 0.689 | 0.249 | 15 |
| RAG | answer_correctness | 0.578 | 0.256 | 15 |

## Paired RAG vs baseline

| Metric | n | RAG | Baseline | Difference | 95% CI | t p | Wilcoxon p |
|---|---:|---:|---:|---:|---|---:|---:|
| answer_relevancy | 15 | 0.689 | 0.783 | -0.094 | [-0.264, +0.062] | 0.291977 | 0.198123 |
| answer_correctness | 15 | 0.578 | 0.228 | +0.350 | [+0.229, +0.472] | 9.6e-05 | 6.1e-05 |

## Refusal rates

| System | Answerability | Refused | Questions | Rate |
|---|---|---:|---:|---:|
| Baseline | answerable | 0 | 12 | 0.0% |
| Baseline | unanswerable | 0 | 3 | 0.0% |
| RAG | answerable | 0 | 12 | 0.0% |
| RAG | unanswerable | 0 | 3 | 0.0% |

## Category breakdown

See `category_metrics.csv` and `answerability_metrics.csv` for the full tables.

