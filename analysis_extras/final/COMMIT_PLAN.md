# Commit plan for the capstone (written 2026-11-19)

Nothing here has been run. You run these commands yourself, in order, from `C:\Projects\RAG project`.
Only files that matter for the study and the running app are included. Local logs, scratch folders,
session transcripts and pilot output are now in `.gitignore`, so `git add` will not pick them up.

## Before you start
1. Run `git status --short` and check that no `.env`, `session.json` or `.db` file is listed. All are ignored.
2. A secret scan of the untracked files found no keys or live connection strings. Re-run
   `python analysis_extras/round5/secret_scan.py` right before you push if you change anything.
3. Do not use `git add .` or `git add -A` at the root. Use the paths below.

## Commits (branch feat/frontend)

### 1. Answer quality and guard
```powershell
git add backend/src/modules/answer_quality.py backend/src/modules/prompts.py backend/src/modules/llm.py backend/src/modules/query_handlers.py backend/src/modules/corpus_vocabulary.json backend/src/data backend/scripts/build_corpus_vocabulary.py backend/tests/test_answer_quality.py backend/tests/test_answer_quality_round5.py backend/tests/test_history_and_source_links.py
git commit -m "feat(rag): answerability guard, missing-detail hints, citation source links, seeded generation"
```

### 2. Knowledge base index (12 pages, 157 chunks)
```powershell
git add backend/kb_index backend/src/modules/load_vesctorstore.py
git commit -m "fix(kb): rebuild index with 157 clean chunks from 12 official pages"
```
`git add backend/kb_index` also records the deletion of the old index folder (e6c0acfc...).

### 3. Backend API, database and auth
```powershell
git add backend/src/__init__.py backend/src/core backend/src/database.py backend/src/logger.py backend/src/main.py backend/src/models backend/src/schemas backend/src/modules/evaluator.py backend/sql/init.sql backend/tests/__init__.py backend/tests/conftest.py backend/tests/test_auth_rbac.py backend/Dockerfile backend/README.md
git commit -m "feat(api): session handling, database config, schemas and RBAC tests"
```

### 4. Frontend
```powershell
git add frontend/src package.json package-lock.json neon.ts
git commit -m "feat(frontend): chat UI, staff history, Auth0 sign-in"
```

### 5. Evaluation tooling and the final run
```powershell
git add backend/scripts/evaluate_rag.py backend/scripts/visualize_evaluation.py backend/evaluation/README.md backend/evaluation/dataset_template.csv backend/evaluation/results backend/evaluation/results_dry_run
git commit -m "eval: final 201-question run with metadata, results tables and figures"
```
Note: the old plan said not to commit `backend/evaluation/results/`. That is out of date. These files are the
final run (commit 60f007b, 402 rows) and the thesis numbers come from them.

### 6. Analysis, labels and reproducibility
```powershell
git add analysis_extras/final analysis_extras/*.csv analysis_extras/*.md analysis_extras/*.py analysis_extras/*.json
git add analysis_extras/review_backups
git add analysis_extras/round3 analysis_extras/round4 analysis_extras/round5
git commit -m "analysis: final tables, corrected judge agreement (n=44), labels, held-out and consistency checks"
```
After this command run `git status --short analysis_extras` and unstage anything you do not want
(for example `analysis_extras/round5/legacy_*.py` or one-off `inspect_*.py` files):
`git restore --staged <path>`.

### 7. Docs, deploy files and ignore rules
```powershell
git add .gitignore .env.example docs scripts README.md
git add -A DEPLOYMENT.md deploy
git commit -m "docs: current deploy checklist (Vercel, Render, Neon, DeepInfra), archive stale Azure and Hugging Face docs"
```
`git add -A DEPLOYMENT.md deploy` records that those files were moved into `docs/archive/`.

## Check, then merge and tag (so Section 5.6 can name a real release)
```powershell
git diff --cached --stat        # should be empty after the commits
git status --short              # should show nothing important
cd backend; poetry run pytest; cd ..
git push origin feat/frontend
git checkout main
git merge --no-ff feat/frontend -m "Merge feat/frontend: evaluated capstone version"
git tag -a v1.0.0 -m "Capstone release: results in Chapter 5"
git push origin main --tags
```
`main` is 24 commits behind, so this merge is large. If it conflicts, stop and send me the output.

## Heads up
- The evaluated run recorded `git_dirty: true` at commit 60f007b. After commit 1 to 6 the repository will hold the
  code that was actually evaluated. Say in Section 5.6 that the tagged release contains the evaluated code
  plus the later fixes listed in these commits.
- Do not change hosting settings as part of this. Nothing in these commits touches Render, Vercel, Neon or DeepInfra.
