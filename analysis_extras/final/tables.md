# Final evaluation summary

## Overall RAGAS scores

| System | Metric | Mean | SD | n |
|---|---|---:|---:|---:|
| Baseline | answer_relevancy | 0.778 | 0.139 | 201 |
| Baseline | answer_correctness | 0.235 | 0.131 | 201 |
| RAG | faithfulness | 0.777 | 0.231 | 201 |
| RAG | context_recall | 0.972 | 0.134 | 201 |
| RAG | answer_relevancy | 0.706 | 0.203 | 201 |
| RAG | answer_correctness | 0.618 | 0.208 | 201 |

## Paired RAG vs baseline

| Metric | n | RAG | Baseline | Difference | 95% CI | t p | Wilcoxon p |
|---|---:|---:|---:|---:|---|---:|---:|
| answer_relevancy | 201 | 0.706 | 0.778 | -0.072 | [-0.102, -0.044] | 4e-06 | 1.1e-05 |
| answer_correctness | 201 | 0.618 | 0.235 | +0.383 | [+0.351, +0.414] | 0.0 | 0.0 |

## Refusal rates

| System | Answerability | Refused | Questions | Rate |
|---|---|---:|---:|---:|
| Baseline | answerable | 1 | 195 | 0.5% |
| Baseline | unanswerable | 0 | 6 | 0.0% |
| RAG | answerable | 0 | 195 | 0.0% |
| RAG | unanswerable | 2 | 6 | 33.3% |

## Category breakdown

See `category_metrics.csv` and `answerability_metrics.csv` for the full tables.

