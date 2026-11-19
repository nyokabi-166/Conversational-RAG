# Corpus-vocabulary guard: offline validation

No model calls. The guard was evaluated with the packaged vocabulary built from the
installed 157-chunk / 12-source index (`backend/src/modules/corpus_vocabulary.json`).

## Acceptance sets

| Set | Result |
|---|---|
| Dev answerable false refusals (25) | **0/25 (0.0%)** |
| Dev unanswerable refused (5) | **4/5 (80.0%)** |
| New synthetic unanswerable refused (12) | **10/12 (83.3%)** |
| New under-specified flagged for missing cabin/route (8) | **8/8 (100%)** |

The two synthetic questions not refused are N01 (Asante miles upgrade fee) and
N08 (Wi-Fi free in business). Both topics occur in the corpus, so the lexical
guard cannot tell that the specific fee/free-access detail is absent. They are
documented as ambiguous rather than intended refusals.

## Evaluation-set diagnostic (single read-only pass)

This audit was used once to check for systematic blind spots; no per-question
rules were added for individual questions.

| Set | Result |
|---|---|
| Answerable questions refused (195) | **0/195 (0.0%)** |
| Unanswerable questions refused (6) | **2/6 (33.3%)** |

Refused unanswerable questions: Q157 (machine) and Q189 (eur). Not refused:
Q052 (excess baggage fee), Q100 (pet carrier maximum weight), Q130 (change fee),
Q131 (free Wi-Fi). All four ask for a value or condition whose topic words occur
in the corpus, which is a lexical-coverage limitation, not a retrieval failure.

## Interpretation

The guard now fails only when a distinctive topic word is absent from the **whole
corpus**, not when retrieval misses the right page. This removes the pilot's 86
false refusals on answerable evaluation questions while keeping refusals for
topics the pages never mention. It cannot detect "topic present, specific value
absent" questions; that residual risk is reported in the thesis limitations.
