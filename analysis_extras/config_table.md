# Evaluation configuration (from code, config and saved results)

| Item | Value | Source | Status |
|---|---|---|---|
| Embedding model | sentence-transformers all-MiniLM-L6-v2 (384-dim, typical) | rag_pipeline.py:34-40; evaluate_rag.py:248 | Model verified; dimensions unverified |
| Vector DB | ChromaDB, locked 1.5.9; persisted at backend/data/chroma_db | poetry.lock; CHROMA_PERSIST_DIRECTORY=./data/chroma_db | Verified |
| Indexed corpus | 219 chunks from 10 source HTML files | analysis_extras/chunk_stats.json | Verified (current index) |
| Chunking (evaluated index) | ~1000 chars, 150 overlap (chunks max 999 chars) | load_vesctorstore.py:254-255 + chunk_stats | Inferred from index contents |
| Chunking (rag_pipeline.py PDF path) | 500 chars, 50 overlap | rag_pipeline.py:125-126 | Not used by evaluation |
| Retrieval | Hybrid: lexical top-4 + dense similarity (32 candidates/query), verified-source filter, de-dup, capped at 8 | query_handlers.py:277-330 | Verified |
| k delivered to LLM | 8 chunks (every report row has 8) | evaluation_report.csv | Verified |
| Similarity metric / threshold / reranker | Chroma default distance; no threshold or reranker seen | - | unverified |
| Generation model / provider | meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo / DeepInfra | llm.py:9; report columns | Verified |
| Generation temperature | 0.1 (both conditions) | llm.py:63 | Verified |
| Judge model / provider | google/gemini-3.1-flash-lite / DeepInfra | report columns; evaluate_rag.py:284 | Verified |
| Judge temperature | unverified (evaluator.py:30 shows 0.5 but may not be the judge path) | - | unverified |
| RAGAS version | 0.4.3 (pyproject ^0.4.3, lock 0.4.3) | pyproject.toml:44; poetry.lock | Verified |
| Answer-relevancy strictness | 1 | evaluate_rag.py:ANSWER_RELEVANCY_STRICTNESS; report column | Verified |
| Metrics | faithfulness, context_recall (RAG only); answer_relevancy, answer_correctness (both) | metric_summary.csv | Verified |
| Dataset | backend/evaluation/ragas_kq_dataset_reviewed.csv and dataset.csv, 201 rows each | row counts | Verified; whether the two files are identical is unverified |
| Evaluation run date | unverified (checkpoint folders exist; no dated run log read) | - | unverified |
| Git commit of evaluated code | unverified (could not run git status). Latest commit seen in .git/logs/HEAD: "Fix passenger and staff authentication flow" (bba1657) | .git/logs/HEAD | Check for uncommitted changes yourself |
