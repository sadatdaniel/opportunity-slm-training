# AGENT_PICKUP.md — READ THIS FIRST

You are continuing **Opportunity Intelligence**: a platform that collects
opportunity postings (scholarships, fellowships, internships…), annotates
them with a multi-provider teacher pool, and trains/serves tiny specialist
models (Supra2-100M-based) behind strict typed decision APIs.

**This file is the entry point. Read it top to bottom, then follow §2.**
Current as of 2026-09-26 — if PROJECT_STATUS.md disagrees, trust PROJECT_STATUS.md
and fix this file.

## 0. The 8 non-negotiable rules

1. NEVER commit secrets (`.env`, tokens), the private briefs
   (`opportunity_intelligence_weekend_build*.md` — verify gitignored), or
   model weights (`models/`).
2. NEVER prune/stop/delete Docker or WSL resources this project did not
   create. Project containers are prefixed `opportunity_slm_`.
3. NEVER exceed provider free limits — the pool enforces rolling-24h budgets
   with 0.70-0.85 safety margins (lessons in PROJECT_STATUS.md). One 429
   storm can lock a Gemini key for a full day.
4. Frozen datasets are immutable — never overwrite a version (the builder
   refuses; keep it that way).
5. The test split is touched once per model release.
6. Commit + push after every meaningful milestone; update PROJECT_STATUS.md
   and the §2 snapshot here.
7. Windows env vars do NOT cross into WSL — pass capabilities as ARGUMENTS
   (`colab_train_wsl.sh summarizer`), never as env prefixes.
8. The user's network is unstable (~30-min drops). Everything must be
   resumable: annotation flushes per record, training checkpoints per epoch,
   verification has `--resume`, and Colab runs must Drive-sync (§5).

## 1. Read next, in order

| file | why |
|---|---|
| `PROJECT_STATUS.md` | live state, ops lessons, decisions log |
| `opportunity_intelligence_weekend_build_v3.md` | the spec (private, git-ignored — never commit) |
| `docs/training_methodology.md` + `docs/evaluation_methodology.md` | how/why we train and evaluate |
| `AGENTS.md` | full layout map, all commands, capability-extension checklist |
| `docs/review_guide.md` | the human-review rules (also your rules for judging labels) |
| `experiments/*.md` | every run, including the negative results |

## 2. State snapshot (2026-09-26)

**Corpus**: 4,670 canonical records, 19 productive sources (target: ~10k;
collection waves 5-6 of the plan done; anti-dup layers verified working).
Wave 5 raw records are normalized + deduped but NOT yet annotated — that is
the first action below.

**Annotation**: classify 4,256 usable labels; summarize 4,145+ (all waves
caught up as of last run; the wave-5 additions need one more annotate pass).

**Verification**: astra (gpt-6-astra) + DeepSeek verdicts cover the
pre-wave-5 corpus: consensus = 3,321 confirmed / 640 single-disagreement /
165 unverified / 4 split / 80 gold. New records are queued behind them.
Tiebreak tooling: `--second-pass-provider experiential` (gpt-6-luna).

**Datasets frozen**: classifier v1-v4, summarizer v1-v4 (v4 = biggest:
classifier 1,924/240/241 + 1,279 unseen; summarizer 2,520/315/315 + 691).

**Models**:
- classifier v0.2.0: **84.3% acc, macro F1 0.733, ECE 0.054** — released on
  GitHub. Trained on v2; v4 (bigger, human-polished) awaits the next run.
- summarizer v0.3.0: trained on the user's Colab notebook (dataset v3 +
  fixed single-template prompts). Eval pending — the boundary-drift fix
  (prompts end with `TARGET OUTPUT:\n`) should have killed the mid-sentence
  starts. Eval cell is in PROJECT_STATUS.md §Colab or the chat history
  pattern: build_raw_prompt → generate → section-format/ROUGE-L vs teacher.

**Teacher pool** (config/teachers.yaml): 4× Gemini slots (primary),
OmniRoute gateway (docker `opportunity_slm_omniroute`, port 20128,
auto/best-reasoning + auto/pro-reasoning), OpenRouter (Nemotron Super
120B), Experiential Labs (gpt-6-luna, verified), DeepSeek flash (verifier,
concurrency=2500 — use 64 workers), Z.ai GLM-5.3-Flash (adjudicator,
Coding-Plan endpoint).

## 3. The work queue (top-down; PROJECT_STATUS.md is authoritative)

1. **Summarizer v0.3.0 evaluation** — if the user's Colab run finished:
   run the eval cell (build_raw_prompt + repetition_penalty=1.15, 10 test
   records, section-format/ROUGE-L vs teacher). If format ≥0.6 and ROUGE-L
   >0.22 → release summarizer-v0.3.0 on GitHub + scale data.
2. **Annotate wave-5 additions**: `uv run python -m project.annotate --task
   classify --workers 8` then `--task summarize --workers 8` (resumable).
3. **Verify the new records**: `uv run python -m project.verify_bulk --task
   classify --provider experiential --model gpt-6-astra --workers 64
   --resume --skip-consensus` (DeepSeek fallback chain is automatic).
4. Re-run `project.consensus --task classify --emit-verify-list`, then
   `project.build_dataset --task classify --version vN+1 --consensus
   data/annotations/consensus_classify.jsonl` — consensus-clean data only.
5. Retrain on Colab: `wsl -d Ubuntu-24.04 -u root -- bash
   scripts/colab_train_wsl.sh summarizer` (capability is ARG 1). Evaluate →
   release with before/after table.
6. gpt-6-luna tiebreak on single-disagreements; unresolved → user queue.

## 4. Working on THIS machine (Windows)

- Repo: `C:\Users\sadat\PycharmProjects\llm_training_project` (Git Bash).
  Python via `uv run` ONLY — bare `python` is not on PATH.
- `.env` holds: GEMINI_API_KEY..GEMINI_API_KEY4, OPENROUTER_API_KEY,
  ZAI_API_KEY, DEEPSEEK_API_KEY, EXPERIMENTALLABS_API_KEY,
  OMNI_ROUTER_API_KEY. Never print or commit values.
- **WSL Ubuntu-24.04**: uv + `colab` CLI live there; Google OAuth token at
  `/root/.config/colab-cli/token.json`, GitHub token at
  `/root/.oi_github_token` (never sent to the Colab VM — code moves via
  `git archive` tarballs).
- **Backups**: `bash scripts/backup_repo.sh` → `../oi_backups/` (includes
  the full corpus with sources; keeps last 8). Run after milestones.
- **Review UI**: `uv run streamlit run project/review.py` → localhost:8501
  (needs-review filter; paste-JSON workflow; title field is ignored).
- **OmniRoute**: docker `opportunity_slm_omniroute`, localhost:20128, key
  in `.env` as OMNI_ROUTER_API_KEY. Started with
  `docker start opportunity_slm_omniroute` if stopped.
- **Git Bash quirks**: heredoc patch scripts mangle `\n` (use
  `chr(10)` concatenation or write files whole); `wsl -- bash -c "..."`
  needs `/mnt/c/...` paths inside the quoted command; MSYS mangles some
  paths — test with `ls` first.
- Prior art for API patterns: `C:\Users\sadat\PycharmProjects\keller\scripts`
  (DeepSeek concurrency, OpenRouter headers/reasoning control).

## 5. Colab training (GPU) — the fragile part, handle with care

- Launch: `wsl -d Ubuntu-24.04 -u root -- bash
  /mnt/c/Users/sadat/PycharmProjects/llm_training_project/scripts/colab_train_wsl.sh
  CAPABILITY` (arg, NOT env var — WSL ignores Windows env prefixes).
- `colab exec` defaults to a 30s timeout — the script sets 1800s (setup) /
  7200s (train). Keep those.
- fp32 on T4 (no bf16): summarizer at 1,536 tokens blew 60 min; we train at
  1,024 (98% coverage per reports/token_stats.md).
- If the WebSocket dies mid-run: the kernel often finishes anyway. Wait for
  network, `colab status`, reconnect, probe with `scripts/colab_vm_probe.py`,
  download artifacts — do NOT relaunch before probing.
- OmniRoute needs Google's jupyter-kernel-client FORK, not PyPI's (see
  AGENTS.md §Colab).
- Drive-durable training is wired into the summarizer driver (mount →
  resume-from-checkpoint → atomic `.complete` sync). Extend to the
  classifier driver when convenient.

## 6. When you finish a phase

1. `uv run pytest` (57+ passing — never lower it knowingly).
2. Update PROJECT_STATUS.md + this file's §2 snapshot.
3. `bash scripts/backup_repo.sh`.
4. Commit (conventional message), push.
