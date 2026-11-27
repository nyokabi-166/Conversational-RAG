"""Read-only analysis of evaluation_report.csv and the Chroma index (tasks 4-7).
Writes only into analysis_extras/. Chroma sqlite is opened read-only.
Run: backend\.venv\Scripts\python.exe analysis_extras\analysis.py
"""
import ast, json, re, sqlite3, statistics, random
from pathlib import Path
import pandas as pd

ROOT = Path(r"C:\Projects\RAG project")
OUT = ROOT / "analysis_extras"
REPORT = ROOT / "backend/evaluation/results/evaluation_report.csv"
CHROMA = ROOT / "backend/data/chroma_db/chroma.sqlite3"
SEED = 42

df = pd.read_csv(REPORT)
rag = df[df.system == "RAG"].copy().reset_index(drop=True)
base = df[df.system == "Baseline"].set_index("case_id")
print("rows", len(df), "rag", len(rag), "baseline", len(base))

# ---- Chroma chunk -> source map (read-only) ----
con = sqlite3.connect(f"file:{CHROMA.as_posix()}?mode=ro", uri=True)
rows = con.execute(
    "SELECT id, key, string_value FROM embedding_metadata "
    "WHERE key IN ('chroma:document','source')"
).fetchall()
con.close()
docs, srcs = {}, {}
for i, k, v in rows:
    (docs if k == "chroma:document" else srcs)[i] = v


def norm_src(s):
    s = Path(str(s)).name
    return re.sub(r"^[0-9a-f]{32}_", "", s).strip()


def norm_text(t):
    return " ".join(str(t).split()).casefold()


text2src = {}
for i, t in docs.items():
    text2src.setdefault(norm_text(t), set()).add(norm_src(srcs.get(i, "")))
lens = [len(t) for t in docs.values()]
chunk_stats = dict(
    n_chunks=len(lens), max_chars=max(lens), median_chars=statistics.median(lens),
    p95_chars=sorted(lens)[int(0.95 * len(lens))],
    n_gt_600=sum(l > 600 for l in lens),
    distinct_sources=sorted({norm_src(s) for s in srcs.values()}),
)
(OUT / "chunk_stats.json").write_text(json.dumps(chunk_stats, indent=2), encoding="utf-8")
print("chunk stats", {k: v for k, v in chunk_stats.items() if k != "distinct_sources"})

# ---- Task 4: retrieval metrics ----
def parse_ctx(s):
    try:
        return ast.literal_eval(s)
    except Exception:
        return []


def rel_sources(v):
    if pd.isna(v) or not str(v).strip():
        return set()
    return {norm_src(p) for p in re.split(r"[;|]", str(v)) if p.strip()}


per_q, unmatched = [], 0
for _, r in rag.iterrows():
    ctxs = parse_ctx(r.retrieved_contexts)
    relset = rel_sources(r.source_file)
    ranked_srcs = []
    for c in ctxs:
        s = text2src.get(norm_text(c))
        if s is None:
            unmatched += 1
            s = set()
        ranked_srcs.append(s)
    first = next((i + 1 for i, s in enumerate(ranked_srcs) if s & relset), None) if relset else None
    per_q.append(dict(
        case_id=r.case_id, category=r.category, answerability=r.get("answerability"),
        relevant_source=";".join(sorted(relset)), n_retrieved=len(ctxs),
        first_relevant_rank=first,
        hit_at_3=int(first is not None and first <= 3), hit_at_5=int(first is not None and first <= 5),
        hit_at_all=int(first is not None), rr=(1 / first) if first else 0.0,
        context_recall=r.context_recall, answer_correctness=r.answer_correctness,
    ))
pq = pd.DataFrame(per_q)
pq.to_csv(OUT / "retrieval_per_question.csv", index=False)
ev = pq[pq.relevant_source != ""]
def summ(g):
    return pd.Series(dict(n=len(g), recall_at_3=g.hit_at_3.mean(), recall_at_5=g.hit_at_5.mean(),
                          hit_rate_all_retrieved=g.hit_at_all.mean(), mrr=g.rr.mean()))
overall = summ(ev).to_frame().T.assign(category="ALL (with source label)")
bycat = ev.groupby("category").apply(summ).reset_index()
pd.concat([overall, bycat]).to_csv(OUT / "retrieval_metrics.csv", index=False)
print("unmatched retrieved chunks:", unmatched, "of", int(pq.n_retrieved.sum()))
print(overall.to_string(index=False))

# ---- Task 5: unanswerable review sheet ----
def pair(cid):
    return rag[rag.case_id == cid].iloc[0], base.loc[cid]

un = rag[rag.answerability.astype(str).str.lower().eq("unanswerable") | rag.category.eq("unanswerable")]
sheet = []
for _, r in un.iterrows():
    b = base.loc[r.case_id]
    sheet.append(dict(case_id=r.case_id, question=r.user_input, reference=r.reference,
                      rag_response=r.response, baseline_response=b.response,
                      rag_answer_correctness=r.answer_correctness,
                      baseline_answer_correctness=b.answer_correctness,
                      rag_type="", baseline_type="", safety=""))
pd.DataFrame(sheet).to_csv(OUT / "unanswerable_review.csv", index=False, encoding="utf-8-sig")
print("unanswerable rows:", len(sheet))

# ---- Task 6: validation sample (seed 42) ----
rng = random.Random(SEED)
chosen = set(un.case_id) | set(rag[rag.category == "navigation"].case_id) | set(rag[rag.category == "conditional_table"].case_id)
srt = rag.sort_values("answer_correctness")
chosen |= set(srt.head(10).case_id) | set(srt.tail(10).case_id)
rest = rag[~rag.case_id.isin(chosen)]
need = max(0, 50 - len(chosen))
# proportional allocation across remaining categories
alloc = (rest.category.value_counts() / len(rest) * need).round().astype(int)
for cat, n in alloc.items():
    pool = sorted(rest[rest.category == cat].case_id)
    chosen |= set(rng.sample(pool, min(n, len(pool))))
extra = sorted(set(rest.case_id) - chosen)
while len(chosen) < 50 and extra:
    chosen.add(extra.pop(rng.randrange(len(extra))))
samp = rag[rag.case_id.isin(chosen)].sort_values(["category", "case_id"])
vs = pd.DataFrame(dict(
    case_id=samp.case_id, category=samp.category, question=samp.user_input, reference=samp.reference,
    rag_response=samp.response, baseline_response=[base.loc[c].response for c in samp.case_id],
    ragas_answer_correctness=samp.answer_correctness, ragas_faithfulness=samp.faithfulness,
    ragas_context_recall=samp.context_recall, sampling_seed=SEED,
    my_correct="", my_supported="", my_complete="", notes=""))
vs.to_csv(OUT / "validation_sample.csv", index=False, encoding="utf-8-sig")
print("validation sample size:", len(vs), vs.category.value_counts().to_dict())

# ---- Task 7: error-analysis starter (DRAFT, heuristic) ----
STOP = set("the a an and or of to in for on at is are be by with from that this it as if any not can may will which what when how per each than then only also".split())
def key_tokens(ref):
    toks = re.findall(r"[a-z0-9][a-z0-9.,/'-]*", str(ref).lower())
    out = [t.strip(".,/'-") for t in toks]
    return [t for t in out if t and t not in STOP and (any(ch.isdigit() for ch in t) or len(t) >= 5)]

low = rag.sort_values("answer_correctness").head(40)
rowsE = []
pqi = pq.set_index("case_id")
for _, r in low.iterrows():
    ctx = norm_text(" ".join(parse_ctx(r.retrieved_contexts)))
    kt = key_tokens(r.reference)
    frac = (sum(t in ctx for t in kt) / len(kt)) if kt else float("nan")
    label = "unclear" if kt == [] else ("yes" if frac >= 0.8 else "partial" if frac >= 0.4 else "no")
    rowsE.append(dict(case_id=r.case_id, category=r.category, answer_correctness=r.answer_correctness,
                      context_recall=r.context_recall, faithfulness=r.faithfulness,
                      key_fact_in_context_DRAFT=label, key_token_coverage=round(frac, 2) if kt else "",
                      relevant_source_in_top8=pqi.loc[r.case_id, "hit_at_all"],
                      question=r.user_input, reference=r.reference, rag_response=r.response,
                      my_confirmed_cause="", notes=""))
pd.DataFrame(rowsE).to_csv(OUT / "error_analysis_starter_DRAFT.csv", index=False, encoding="utf-8-sig")
print(pd.DataFrame(rowsE).key_fact_in_context_DRAFT.value_counts().to_dict())
