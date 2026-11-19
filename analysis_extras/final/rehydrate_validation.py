import pandas as pd
from pathlib import Path
import hashlib, json

ROOT = Path(r"C:\Projects\RAG project")
REPORT = ROOT / "backend/evaluation/results/evaluation_report.csv"

# ----- 1. read current validation sample (labels only) -----
val_path = ROOT / "analysis_extras/validation_sample.csv"
val_df = pd.read_csv(val_path, encoding="utf-8-sig")
case_ids = val_df["case_id"].tolist()
my_correct = val_df["my_correct"].tolist()

# ----- 2. read final report -----
final = pd.read_csv(REPORT)
rag = final[final.system == "RAG"].set_index("case_id")
base = final[final.system == "Baseline"].set_index("case_id")

# ----- 3. build rehydrated rows preserving label order -----
rows = []
for cid in case_ids:
    r = rag.loc[cid]               # RAG row for this case
    b = base.loc[cid]              # Baseline row
    row = {
        "case_id": cid,
        "category": r["category"],
        "question": r["user_input"],
        "reference": r["reference"],
        "rag_response": r["response"],
        "baseline_response": b["response"],
        "ragas_answer_correctness": float(r["answer_correctness"]),
        "ragas_faithfulness": float(r["faithfulness"]),
        "ragas_context_recall": float(r["context_recall"]),
        "sampling_seed": 42,
        "my_correct": int(my_correct[case_ids.index(cid)]),
        "my_supported": "",
        "my_complete": "",
        "notes": "",
    }
    rows.append(row)

new_df = pd.DataFrame(rows, columns=[
    "case_id", "category", "question", "reference",
    "rag_response", "baseline_response",
    "ragas_answer_correctness", "ragas_faithfulness",
    "ragas_context_recall", "sampling_seed",
    "my_correct", "my_supported", "my_complete", "notes"
])

# ----- 4. write output -----
out_path = ROOT / "analysis_extras/validation_sample.csv"
new_df.to_csv(out_path, index=False, encoding="utf-8-sig")
print("Wrote validation sample:", len(new_df), "rows")

# ----- 5. compute manifest protected hash (case_id only) -----
payload = "\n".join(case_ids)
sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
print("Protected SHA-256:", sha)

# ----- 6. write manifest entry for validation -----
manifest_entry = {
    "validation_sample.csv": {
        "row_count": len(new_df),
        "case_ids": case_ids,
        "protected_columns": ["case_id"],
        "protected_sha256": sha
    }
}

manifest_path = ROOT / "analysis_extras/review_backups/protected_columns.json"
# load existing manifest if any, then overwrite with correct schema
manifest = {}
if manifest_path.is_file():
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}

manifest.update(manifest_entry)
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("Manifest updated")