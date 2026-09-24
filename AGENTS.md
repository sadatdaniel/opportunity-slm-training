# AGENTS.md — Guide for Future Agent Sessions

Read this file first. It orients you in one page; `PROJECT_STATUS.md` holds
the live state; `opportunity_intelligence_weekend_build_v3.md` (private,
git-ignored) is the authoritative specification.

## What this project is

An end-to-end platform that (a) collects opportunity postings (scholarships,
fellowships, internships...), (b) turns them into teacher-annotated datasets,
and (c) trains/serves very small specialist models (Supra2-100M-based) behind
strict typed decision APIs. Capabilities: summarizer, classifier (Choice),
Noul (binary), batched System-One (`/v1/systemone`). NO generic chat endpoints.

## Read in this order

1. `PROJECT_STATUS.md` — current phase, what's done, human actions, decisions log
2. `opportunity_intelligence_weekend_build_v3.md` — spec (private; NEVER commit; verify gitignored)
3. `docs/training_methodology.md` + `docs/evaluation_methodology.md` — how we train/evaluate
4. `reports/pilot_report.md`, `reports/token_stats.md` — measured facts
5. `experiments/` — one report + manifest per run; negative results included

## Golden rules

- Never commit: secrets, `.env`, `opportunity_intelligence_weekend_build*.md`,
  model weights (`models/`), raw collected data (`data/raw|normalized|curated`).
  Manifests/reports/dataset-splits ARE committed (repo is private).
- Never prune/stop/delete Docker or WSL resources this project didn't create.
- Every training run: stable run_id, manifest, frozen dataset version + hashes,
  seed. Resume via `--resume-from-checkpoint`; run identity continues.
- Dataset versions are immutable: freeze v2 instead of mutating v1.
- Test splits are frozen; tune on validation only.
- Windows storage is tight (~12GB free): keep models/caches on Google VMs,
  download only artifacts.

## Layout (where things live)

```
project/            data pipeline CLI (see Commands below)
collectors/         polite fetcher + per-source collectors (cache, robots, rate limit)
training/common/    experiment manifests, dataset loading, metrics/calibration, model registry
training/classifier|summarizer|noul|systemone/   per-capability code + config.yaml
service/main.py     FastAPI: /health /version /v1/capabilities /v1/summarize /v1/categorize /v1/noul /v1/systemone
config/             taxonomy_v1.yaml, teachers.yaml (provider pool), task_registry.yaml, noul_families.yaml
prompts/            versioned teacher prompts (summarizer_v2, classifier_v1)
data/               raw -> normalized -> deduped -> curated; annotations; manifests (corpus_v1.yaml)
datasets/           frozen splits per capability+version (classifier/v1)
models/             trained artifacts, versioned (classifier/v0.1.0) — git-ignored
experiments/        run manifests + markdown reports
scripts/            WSL/Colab automation, backup_repo.sh
colab/              browser-notebook path (colab_train.ipynb)
docs/               methodology + learning notes
```

## Commands (all via `uv run ...` from repo root)

Data: `project.sources.registry` · `project.sources.inventory` ·
`project.collect --all --methods wp_rest,rss` · `project.normalize` ·
`project.dedupe` · `project.freeze_corpus` · `project.build_noul_set`

Measurement: `project.token_stats` · `project.audit`

Annotation (teacher pool: 4 Gemini slots primary, OpenRouter second opinion,
Z.ai adjudicator via Coding-Plan endpoint, DeepSeek verifier, legacy TEACHER_*):
`project.annotate --task classify [--pilot]` · `project.verify_annotations`
(concurrent; DeepSeek limits are CONCURRENCY=2500, not RPM — set
max_concurrency in config/teachers.yaml)

Datasets + training: `project.build_dataset --task classify` ·
`training.classifier.train [--smoke|--resume-from-checkpoint DIR]` ·
`training.classifier.evaluate` · `training.noul.evaluate` ·
`training.systemone.benchmark_batch`

Review UI: `uv run streamlit run project/review.py` (human gate before dataset
freezes; supports disputing primary/secondary/ambiguity/reason; corrections
preserve the teacher's original output)

## Colab GPU workflow (training happens there; local machine is weak)

- WSL Ubuntu-24.04 has uv + `colab` CLI; Google OAuth token at
  `~/.config/colab-cli/token.json`; GitHub token at `~/.oi_github_token`
  (never sent to the VM; code moves via `git archive` tarballs).
- Known pitfall: colab-cli needs **Google's fork** of jupyter-kernel-client
  (PyPI package is a name collision without `JupyterSubprotocol`):
  `uv pip install --python <tool-venv-python> "jupyter-kernel-client @ git+https://github.com/googlecolab/jupyter-kernel-client.git"`
- `colab exec --timeout N` defaults to 30s — pass large N for installs/training.
- Pattern: `colab new -s oi-trainer --gpu T4` → package+upload → setup → train
  → download artifacts → **`colab stop`** (quota bills connection time).
- See `scripts/colab_train_wsl.sh`, `scripts/colab_vm_setup.py`, `scripts/colab_vm_train.py`.

## Backups (GitHub is not the only copy)

`bash scripts/backup_repo.sh` → timestamped archives in `../oi_backups/`
(secrets excluded; keeps last 8). Run after meaningful milestones. The Colab
session, WSL, and local venv are all disposable; the repo + backup archive +
Drive-side checkpoints are the durable state.

## How to add a new capability (checklist)

1. `training/<capability>/{__init__,train,evaluate}.py + config.yaml`
   (import Experiment, dataset loaders, model_registry — don't reinvent)
2. Dataset: extend `project/annotate.py` (new prompt version) or a dedicated
   builder; `project/build_dataset.py` CAPABILITY_DIR mapping; freeze v1
3. Register in `config/task_registry.yaml` (model path, type, endpoint)
4. API: add typed endpoint(s) in `service/main.py` reusing the SystemOne
   engine for decision primitives — never expose generation
5. Tests: fixture-based, offline (tiny GPT2 + cached tokenizer pattern in
   `tests/test_systemone.py`); PROJECT_ROOT regression test if adding modules
6. Update `PROJECT_STATUS.md` + methodology docs + experiments/ report
