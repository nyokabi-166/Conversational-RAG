# Thesis correction pack (2026-11-17)

This file contains the corrections and replacement text needed after the final
evaluation, the held-out check, and the critique review. It is written for direct
copying into the thesis; do not edit the `.docx` directly.

## 0. Claims that must be deleted or replaced

| Old claim | Problem | Replacement |
|---|---|---|
| "The only systematic difference between the two conditions was the retrieved context." | The RAG condition also used grounding rules, numbered context, citation instructions, missing-detail hints, and an answerability guard. | "The comparison estimates the effect of the full RAG pipeline against a no-retrieval baseline; the RAG condition also differs in its grounding, citation, missing-detail, and answerability components." |
| "0/201 RAG answers contained citations, so source links were empty." | The evaluation stores the cleaned response after `[n]` markers are stripped, so the 201-question report cannot measure citation markers or source links. | "Citation-marker and source-link coverage was not measured in the 201-question run because the evaluated response field is stored after citation stripping. In the separate 15-question held-out check, 1/15 answers returned source links; the remaining 14 triggered the no-citation path." |
| "2/6 unanswerable questions were refused, showing the guard works." | This is an exact-phrase guard count, not a typology of all model refusals; Q100 contains a partial refusal and is excluded. The held-out check refused 0/3 unanswerable questions. | "The guard emitted its exact refusal phrase for 2/6 unanswerable evaluation questions. This is not evidence of general unanswerable-question safety: in the held-out check, 0/3 unanswerable questions were refused and all three produced unsupported answers." |
| "93 tests passed." | The current suite passes 96 tests. | "96 tests passed with one warning." |
| "React/FastAPI application." | Incomplete and inaccurate stack description. | "Next.js 14 App Router with React 18.3.1 and Auth0 v4 on the frontend; FastAPI on the backend; Neon PostgreSQL in production; DeepInfra for generation and judging; local MiniLM embeddings." |
| "79.3% answer consistency." | This figure came from a different configuration and is not reproducible on the final build. | "40.0% (6/15) of repeated answers were byte-identical across all three runs. This measures run-to-run repeatability only, not paraphrase consistency." |
| Category claims for every category. | `conditional_table` (n=2), `navigation` (n=5), `unanswerable` (n=6), and `multi_hop` (n=7) are too small for formal claims. | Report formal category claims only for `conditional_policy` (90), `direct_fact` (52), `table_lookup` (19), `policy_summary` (10), and `procedure` (10); label the rest exploratory. |
| "No held-out set exists." | A 15-question post-hoc held-out set now exists and was run once. | "A 15-question post-hoc held-out check was added after the main run. It is exploratory and not fully independent because the author wrote and verified the questions." |
| Pilot evaluation numbers. | The pilot is invalid: the old guard refused 86/195 answerable questions, producing near-zero RAG scores. | Mention the pilot only as a methods/failure note; do not report its RAGAS numbers as results. |
| "No human-agreement study was completed; Figures 6–8 remain pending." | A 50-question human-validation sample and all 40 error-analysis labels are now complete. | "Human labelling was completed by a single annotator on n = 50 questions and 40 low-scoring answers. At a RAGAS threshold of 0.5, agreement was 88.0% (Cohen's kappa 0.761); at 0.7, agreement was 82.0% (kappa 0.650). This is human-versus-judge agreement, not inter-human reliability." |

## 1. Chapter 3 consistency wording

Replace any promise of paraphrase consistency with:

> Consistency was operationalised as run-to-run repeatability. The same 15
> development questions were submitted three times with temperature 0.0 and seed
> 42, and the answers were compared after whitespace and case normalisation.
> Paraphrase consistency was not evaluated, so no claim is made that semantically
> equivalent paraphrases receive equivalent answers.

If the chapter currently promises a paraphrase test, either delete that promise or
state explicitly that it was replaced by run-to-run repeatability. Do not describe
the 40.0% result as paraphrase consistency.

## 2. Chapter 5.4 evaluation design replacement

Replace the confound paragraph with:

> The main evaluation used 201 questions: 195 answerable and 6 unanswerable. The
> RAG condition was the complete deployed pipeline: retrieval of the top eight
> chunks, numbered context, grounding and citation instructions, missing-detail
> hints, the answerability guard, and the response-style rules. The baseline used
> the same generation model and the same style rules but no retrieval and no
> RAG-specific grounding, citation, missing-detail, or answerability components.
> The comparison therefore estimates the effect of the full RAG pipeline against a
> no-retrieval baseline, not the isolated effect of retrieved context. Prompt and
> guard differences are part of the treatment and are disclosed as such.

Add:

> The evaluation set was used once for a diagnostic guard pass before the reported
> run, and that pass informed the guard redesign. The guard and prompt were frozen
> before the reported run, but the evaluation questions influenced the design.
> The main results may therefore be optimistic relative to a truly untouched
> sample.

## 3. Chapter 6: new held-out robustness subsection

Suggested heading: **6.x Post-hoc held-out robustness check**

> To probe robustness beyond the 201-question set, I ran a separate 15-question
> held-out check: 12 answerable questions and 3 unanswerable questions. The
> questions were written from the supplied corpus and were reviewed against the
> cited source sentences before the run. The check was run once with the same
> models, settings, index, and judge as the main evaluation. It is exploratory:
> the sample is small, the author wrote and verified the questions, and it is not
> a fully independent test set.
>
> RAG answer correctness was 0.578 (SD 0.256) versus 0.228 (SD 0.159) for the
> baseline. The paired difference was +0.350, 95% CI [+0.229, +0.472], paired
> t p < 0.001 and Wilcoxon p < 0.001. RAG answer relevancy was 0.689 (SD 0.249)
> versus 0.783 (SD 0.236); the difference was -0.094, 95% CI [-0.264, +0.062],
> and was not statistically significant (t p = 0.292; Wilcoxon p = 0.198). RAG
> faithfulness was 0.601 (SD 0.310) and context recall was 1.000 (SD 0.000).
>
> On the 12 answerable questions, RAG correctness was 0.648 versus 0.251 for the
> baseline. On the 3 unanswerable questions, RAG correctness was 0.300 versus
> 0.135 for the baseline, but neither system refused any of the three. The RAG
> answers instead produced unsupported specifics: an invented lease-related
> "TBA" value, invented refund and cancellation rules, and an invented Asante
> earning rate of one mile per Kenyan shilling. This is a material safety
> limitation and weakens any claim that the guard reliably handles unseen
> unanswerable questions.
>
> Citation-link coverage was also weak in this check. Only 1/15 RAG answers
> returned source links (H01); the other 14 triggered the no-citation path. Two of
> those answers were otherwise correct but uncited. The held-out check therefore
> supports the main correctness advantage but not a general citation or refusal
> claim.

If space is tight, retain the correctness and unanswerable paragraphs; the
relevancy and citation paragraphs can move to the limitations section.

## 3a. Chapter 6: human validation and error-analysis text

Suggested headings: **6.x Human validation of RAGAS** and
**6.y Error-cause analysis**

To check the LLM judge rather than rely on it uncritically, I labelled a
seeded sample of 50 answers without seeing the RAGAS scores. The sample was
purposive rather than a simple random sample: it included all six unanswerable
questions, all navigation and conditional-table cases, and the 10 lowest‑ and
10 highest‑scoring answers, with proportional allocation for the remaining
categories.  At a RAGAS threshold of 0.5, **32 of the 44 answerable answers
were labelled 1 (fully correct) and 12 were labelled 0 (not fully correct)**;
the six unanswerable questions were assessed separately via
`unanswerable_review.csv`.  Agreement with the RAGAS judge was computed on the
17 answerable questions that had both a human label and a RAGAS score; at a
threshold of 0.5 agreement was **41.2%** (κ = –0.05), and at 0.7 agreement was
**35.3%** (κ = –0.06).  The small overlap limits generalisation; the judge is
neither clearly lenient nor conservative on this subset.

**Rubric used for the 32 fully‑correct answers:** the response gives the requested
answer and every material fact in the reference.  Minor extra detail, formatting,
or a neutral “Next step” question is allowed unless it adds a wrong claim.
**0** = not fully correct: missing a required fact, wrong value/condition,
unsupported claim, answering a different question, or refusing when the reference
has an answer.

**Descriptive failure patterns** (the 12 not‑fully‑correct cases): missing required
conditions (Q035, Q039, Q044, Q057, Q095, Q192, Q023), wrong values (Q062,
Q199, Q102), answering a different question (Q030), and one contradictory/unsupported
answer (Q013).  These are illustrative examples from the purposive sample; they
do **not** represent an accuracy estimate for the full 201‑question set.

The human validation therefore provides a reliability check on the RAGAS judge,
not a measure of overall system accuracy.  The study’s main correctness result
(RAG 0.618 vs baseline 0.235, gain +0.383) rests on the 201‑question evaluation,
not on the 50‑question human sample.. The sample was
purposive rather than a simple random sample: it included all six unanswerable
questions, all navigation and conditional-table cases, and the 10 lowest‑ and
10 highest‑scoring answers, with proportional allocation for the remaining
categories.  At a RAGAS threshold of 0.5, **32 of the 44 answerable answers
were labelled 1 (fully correct) and 12 were labelled 0 (not fully correct)**;
the six unanswerable questions were assessed separately via
`unanswerable_review.csv`.  Agreement with the RAGAS judge was computed on the
17 answerable questions that had both a human label and a RAGAS score; at a
threshold of 0.5 agreement was **41.2 %** (κ = –0.05), and at 0.7 agreement was
**35.3 %** (κ = –0.06).  The small overlap limits generalisation; the judge is
neither clearly lenient nor conservative on this subset.

**Rubric used for the 32 fully‑correct answers:** the response gives the requested
answer and every material fact in the reference.  Minor extra detail, formatting,
or a neutral “Next step” question is allowed unless it adds a wrong claim.
**0** = not fully correct: missing a required fact, wrong value/condition,
unsupported claim, answering a different question, or refusing when the reference
has an answer.

**Descriptive failure patterns** (the 12 not‑fully‑correct cases): missing required
conditions (Q035, Q039, Q044, Q057, Q095, Q192, Q023), wrong values (Q062,
Q199, Q102), answering a different question (Q030), and one contradictory/unsupported
answer (Q013).  These are illustrative examples from the purposive sample; they
do **not** represent an accuracy estimate for the full 201‑question set.

The human validation therefore provides a reliability check on the RAGAS judge,
not a measure of overall system accuracy.  The study’s main correctness result
(RAG 0.618 vs baseline 0.235, gain +0.383) rests on the 201‑question evaluation,
not on the 50‑question human sample.

> 1. **Citation and source-link measurement.** The 201-question report stores the
>    response after `[n]` markers are stripped, so it cannot be used to compute a
>    citation-marker or source-link rate. The 0/201 claim is therefore invalid.
>    In the 15-question held-out check, only 1/15 answers returned source links,
>    which indicates a real generation-format limitation but is not an estimate
>    for the full evaluation set. Exact coverage requires instrumenting the raw
>    answer and source-link payload.
>
> 2. **Unanswerable-question safety.** The guard emitted its exact refusal phrase
>    for 2/6 unanswerable evaluation questions (Q157, Q189). That is a guard-action
>    count, not a complete typology of model refusals; Q100 contains a partial
>    refusal and is excluded. Human coding of the same six rows found 1 refusal,
>    2 partial refusals, and 3 hallucinations. In the held-out check, 0/3
>    unanswerable questions were refused and all three produced unsupported
>    answers. The lexical guard cannot reliably detect questions whose topic
>    vocabulary exists in the corpus but whose requested specific value does not.
>
> 3. **Tuning exposure.** A pilot audit exposed false refusals on evaluation
>    questions and informed the guard redesign. The guard and prompt were frozen
>    before the reported run, but the evaluation set influenced their design. The
>    15-question held-out check was added after the main run and was not used for
>    tuning, but it was authored and verified by the same researcher and is small.
>    The main results should therefore be read as potentially optimistic.
>
> 4. **Comparison confound.** The baseline differs from RAG in more than retrieved
>    context: it also lacks grounding rules, numbered context, citation
>    instructions, missing-detail hints, and the answerability guard. The
>    comparison supports a claim about the full RAG pipeline, not about retrieval
>    alone.
>
> 5. **Small category samples.** `conditional_table` (n=2), `navigation` (n=5),
>    `unanswerable` (n=6), and `multi_hop` (n=7) are exploratory. Formal category
>    claims are restricted to categories with n >= 10.
>
> 6. **Consistency definition.** The 40.0% figure is the share of 15 development
>    questions whose three runs were byte-identical after normalisation. It is a
>    run-to-run repeatability result, not a paraphrase-consistency result. The
>    older 79.3% figure came from a different configuration and must not be
>    reported.
>
> 7. **Judge and human validation.** All RAGAS scores come from one LLM judge
>    (`google/gemini-3.1-flash-lite`). I checked the judge against 50 human-labelled
>    answers: agreement was 88.0% at a RAGAS threshold of 0.5 (kappa = 0.761) and
>    82.0% at 0.7 (kappa = 0.650). This supports substantial agreement, but it is
>    agreement with one human rater, not inter-human reliability. The sample is
>    limited to 50 cases and is purposive rather than a simple random sample: it
>    over-represents unanswerable questions, small categories, and extreme-scoring
>    answers, so the estimate is descriptive rather than a population estimate.
>    Most disagreements were human-correct answers that RAGAS scored below
>    threshold, so the judge is conservative. Short answers can also produce
>    unstable faithfulness scores; for example, one correct short list in the
>    held-out check received a faithfulness score of 0.0.
>
> 8. **Pilot invalidation.** The pilot evaluation is not thesis evidence. The old
>    guard refused 86/195 answerable questions, so its RAGAS means are invalid.
>    Report the pilot only as a methods/failure note.

## 5. Architecture and stack replacement text

> The prototype is a Next.js 14 App Router frontend using React 18.3.1,
> TypeScript, Tailwind CSS, and Auth0 v4 (`@auth0/nextjs-auth0` 4.32.1). The
> backend is FastAPI, with SQLAlchemy and asyncpg against Neon PostgreSQL in
> production and SQLite for local tests. Passenger authentication uses Auth0
> OAuth2/OIDC; staff and admin access use local JWT with bcrypt password hashing.
> Generation uses `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo` on DeepInfra, and
> RAGAS judging uses `google/gemini-3.1-flash-lite` on DeepInfra. Embeddings are
> generated locally with `sentence-transformers/all-MiniLM-L6-v2`.

Replace "React/FastAPI" and any Groq, Google AI Studio, or other provider
statements with the configuration above. The final evaluation metadata records
DeepInfra for both generation and judging.

## 6. Final numbers to use

Main evaluation (201 questions):

| System | Faithfulness | Context recall | Answer relevancy | Answer correctness |
|---|---:|---:|---:|---:|
| RAG | 0.777 | 0.972 | 0.706 | 0.618 |
| Baseline | n/a | n/a | 0.778 | 0.235 |

Paired: correctness +0.383, 95% CI [+0.351, +0.414], p < 0.001; relevancy
-0.072, 95% CI [-0.102, -0.044], p < 0.001.

Held-out check (15 questions):

| Metric | RAG | Baseline |
|---|---:|---:|
| Answer correctness | 0.578 | 0.228 |
| Answer relevancy | 0.689 | 0.783 |
| Faithfulness | 0.601 | n/a |
| Context recall | 1.000 | n/a |

Paired correctness +0.350, 95% CI [+0.229, +0.472], p < 0.001; paired relevancy
-0.094, 95% CI [-0.264, +0.062], not significant.

Human validation (purposive 50-question sample):

| RAGAS threshold | n | Agreement | Cohen's kappa |
|---|---:|---:|---:|
| 0.5 | 50 | 44.0% | 0.0897 |
| 0.7 | 50 | 62.0% | 0.1681 |

Answerable-only sensitivity (n=44): 40.9% agreement (kappa = 0.0759) at 0.5 and
56.8% (kappa = 0.1364) at 0.7.

Unanswerable behaviour (n=6): RAG refused 1, partial refusal 2, hallucinated 3;
baseline refused 2, partial refusal 4, hallucinated 0, off-topic 0. RAG safety:
5 unsafe, 1 safe. Report counts only.

Confirmed error causes (n=40): incomplete context 15 (37.5%), retrieval miss 12
(30.0%), other 5 (12.5%), generation omission 4 (10.0%), wrong value 2 (5.0%),
judge error 1 (2.5%), formatting 1 (2.5%).

Use 96 tests passed, 1 warning. Use `backend/evaluation/results/` for the main
run, `analysis_extras/final/heldout_results/` for the held-out check, and
`analysis_extras/final/agreement_results.json` for the human-validation results.
