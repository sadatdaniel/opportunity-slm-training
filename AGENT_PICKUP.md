# AGENT_PICKUP.md — READ THIS FIRST

You are continuing the **Opportunity Intelligence** project: a platform that
collects opportunity postings (scholarships, fellowships, internships…),
annotates them with a multi-provider teacher pool, and trains/serves tiny
specialist models (Supra2-100M-based) behind strict typed decision APIs.

**This file is the entry point. Everything else hangs off it. Read top to
bottom, then follow the pointers.**

## 0. Non-negotiable rules

1. NEVER commit secrets (`.env`, tokens), `opportunity_intelligence_weekend_build*.md`
   (private briefs — verify gitignored), or model weights (`models/`).
2. NEVER prune/stop/delete Docker or WSL resources this project did not create.
3. NEVER exceed provider free limits — the pool enforces rolling-24h budgets
   with safety margins (see lessons in PROJECT_STATUS.md §Teacher-pool operations).
   One 429 storm can lock a Gemini key for a full day.
4. Frozen datasets are immutable: never overwrite a version, build the next one.
5. The test split is touched once per model release.
6. Commit + push after every meaningful milestone. Update PROJECT_STATUS.md.

## 1. Read next (in order)

| file | why |
|---|---|
| `PROJECT_STATUS.md` | live state: phase, done/remaining, human actions, ops lessons |
| `opportunity_intelligence_weekend_build_v3.md` | the authoritative spec (private, git-ignored — never commit) |
| `docs/training_methodology.md` + `docs/evaluation_methodology.md` | how we train/evaluate and why |
| `AGENTS.md` | layout map, all commands, capability-extension checklist |
| `experiments/*.md` | every run so far, including negative results |
| `reports/pilot_report.md`, `reports/token_stats.md` | measured teacher + tokenizer facts |

## 2. Where the project stands (snapshot — verify against PROJECT_STATUS.md)

- **Corpus**: 3,296 canonical records fully annotated (classification) + a
  running targeted-collection wave into weak classes (postdoc/grant/award/
  fellowship category feeds — discovered category IDs persisted in recipes).
- **Classifier v0.2.0**: 84.3% accuracy / macro F1 0.733 / ECE 0.054 on the
  frozen v2 test split (v0.1.0 was 17.6% at 14.6× less data). Artifact:
  `models/classifier/v0.2.0`. Next data milestone: dataset v3 after human
  review of ~33 newly flagged records (queue live) + weak-class wave.
- **Teacher pool**: 4× Gemini (primary, rolling-24h budgets), OmniRoute
  gateway (self-hosted docker `opportunity_slm_omniroute`, port 20128,
  `auto/best-reasoning` second opinion + `auto/pro-reasoning` verifier),
  OpenRouter (Nemotron Super 120B), DeepSeek (verifier, credit low),
  Z.ai GLM-5.3-Flash (adjudicator, Coding-Plan endpoint).
- **Summarizer**: prompt v2 ready; 300-record pilot may be running or done —
  check `data/annotations/summarize.jsonl`; next = SFT training on Colab
  (`training/summarizer/train.py`) + field-level benchmark (§22A).
- **Noul**: prototype evaluator + families (incl. interdisciplinary and
  residency questions) in `config/noul_families.yaml`; trained model awaits
  extraction-facts training data.
- **Review queue**: Streamlit `project/review.py` — human decisions land in
  `data/annotations/classify.jsonl`; paste-JSON workflow supported.

## 3. Immediate work queue (pick top-down; verify in PROJECT_STATUS.md)

1. Summarizer pilot: `uv run python -m project.annotate --task summarize --pilot --limit 300`
   (runs in background if already started — check `data/annotations/summarize.jsonl`).
2. Human-review queue: `uv run streamlit run project/review.py` (needs-review
   filter) — user does this; never auto-accept flagged records.
3. Targeted collection into weak classes:
   `uv run python -m project.collect --all --methods wp_rest --targeted "postdoc,exchange,summer-school,grants,awards" --limit 60`
4. After new annotations: `uv run python -m project.normalize && uv run python -m project.dedupe`
   then `uv run python -m project.build_dataset --task classify --version vN+1` (never overwrite).
5. Retrain on Colab: `wsl -d Ubuntu-24.04 -u root -- bash scripts/colab_train_wsl.sh`
   (needs the WSL setup from AGENTS.md; watch the `--timeout` pitfall).

## 4. Known pitfalls (full list in PROJECT_STATUS.md §lessons)

- `colab exec` defaults to a 30s timeout — always pass `--timeout`.
- OmniRoute needs **Google's fork** of jupyter-kernel-client, not PyPI's.
- Keyed Streamlit widgets ignore their `value` param on later renders.
- Anthropic-style path issues: `project/*.py` modules use `parents[1]`,
  `project/sources/*.py` use `parents[2]` — covered by tests/test_paths.py.
- Google RPD resets are NOT UTC midnight — hence rolling-24h budgets.

## 5. When you finish a phase

1. Run the test suite (`uv run pytest`).
2. Update PROJECT_STATUS.md (phase, snapshot, next actions).
3. Update this file's §2 snapshot if it drifted.
4. `bash scripts/backup_repo.sh` (local backup beyond GitHub).
5. Commit with a conventional message; push.
