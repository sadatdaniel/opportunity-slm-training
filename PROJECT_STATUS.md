# Project Status

Single source of truth for build state, so any future session or agent can
resume exactly where work stopped. Update after every milestone.

- **Specification**: `opportunity_intelligence_weekend_build.md` (private, git-ignored, never commit)
- **Current phase**: 4 — Annotation-ready corpus complete; awaiting teacher API key
- **Blocking human actions**: teacher API credential (see below)
- **Current commit**: see `git log -1` (updated at each milestone)

## Corpus state (after collection wave 2)

- 4,281 raw records (with full provenance) from 21 recipes provisioned
- 3,335 normalized English records; 3,296 canonical after dedup (39 duplicates
  in 33 groups, 4 cross-source) from **16 productive sources**
- word counts: p50 484, p90 2658; 61% fit the 600-word summarizer input budget
- 53 raw lines corrupted by an interrupted early process are skipped by normalize
- per-source distribution: `reports/normalization_report.md`
- 14 sources blocked (403/robots) — documented in inventory, not bypassed

## Human actions required

1. **Teacher API credential** (annotation is fully built and waiting):
   copy `.env.example` → `.env` and set `TEACHER_BASE_URL` (OpenAI-compatible),
   `TEACHER_API_KEY`, `TEACHER_MODEL`. Then:
   `uv run python -m project.annotate --task classify` and `--task summarize`
2. (Later, before Colab training) WSL2 only has the docker-desktop distro; the
   Colab CLI needs a real Linux distro — `wsl --install Ubuntu` requires user action.

## Completed

- [x] Build brief read; git hygiene verified before first commit
- [x] Private repo `sadatdaniel/opportunity-slm-training`, pushed at every milestone
- [x] Registry normalizer (106 sources), polite fetcher (cache/rate-limit/robots)
- [x] Source inventory: 14 wp_rest / 7 rss / 54 html / 17 review / 14 blocked
- [x] Collector framework (WP REST, RSS+detail, recipe-driven HTML) + 39 recipes
- [x] Collection waves 1-2; normalization; layered dedup with group evidence
- [x] Taxonomy v1 (`config/taxonomy_v1.yaml`, 12 categories + aliases, rationale
      in `reports/taxonomy_v1.md`) from corpus evidence
- [x] Teacher annotation pipeline + versioned prompts (summarizer_v1, classifier_v1)
- [x] Dataset builder: gold/silver/quarantine tiers, duplicate-group-aware splits,
      unseen-source holdout, hashed manifests, frozen test sets (26 tests passing)
- [x] Ponytail (user plugin) simplification pass; PROJECT_ROOT regression fixed

## Remaining

1. **Run annotation** once `.env` is configured (classifier first — larger corpus use)
2. Human review queue UI (Streamlit, brief §18) — build when annotations exist
3. `python -m project.build_dataset --task classify` → first classifier dataset v1
4. HTML recipes for the 54 html sources (EURAXESS, DAAD, after_school_africa next)
   to push the corpus past 4k canonical records for summarizer scale-up
5. Token-length statistics with the real Supra tokenizer (brief §21)
6. Baselines: base Supra2-100M summarization + classification (incl. Von baseline)
7. Colab/WSL training workflow; Supra classifier + summarizer experiments
8. FastAPI service (strict endpoints), Docker files, regression suite, final report

## Remaining (build-brief order)

1. Collector framework wiring per source + fixture-based parser tests; collect corpus
   (~4,000–8,000 unique opportunities target) with per-source adaptive quotas
2. Normalization/cleaning pipeline; layered deduplication with duplicate groups
3. Taxonomy discovery → `reports/proposed_categories.md`, `reports/taxonomy_v1.md`,
   `config/taxonomy_v1.yaml`
4. Teacher annotation pipeline (provider-configurable, env-var secrets) for
   summarization + classification; review metadata separate from student targets
5. Human review queue (small local UI), quality tiers: gold / silver / quarantine
6. Dataset builders + leakage-aware splits (duplicate-group aware, frozen test set,
   unseen-source eval split)
7. Token-length statistics with the real Supra tokenizer (p50…p99, fit rates)
8. Baseline evaluations before training (base model summarization + classifier baselines,
   Von/System-One baseline)
9. Colab GPU training workflow (WSL2 required for google-colab-cli; note: WSL currently
   only has the docker-desktop distro — may need `wsl --install Ubuntu`, requires user)
10. Supra classifier training + calibration (temperature scaling, ECE/Brier)
11. Supra summarizer training (full FT vs LoRA comparison)
12. FastAPI service: `/health`, `/version`, `/v1/capabilities`, `/v1/summarize`, `/v1/categorize`
    (strict endpoint boundaries, no generation endpoints)
13. Docker: `Dockerfile.api`, `Dockerfile.dev`, `docker-compose.yml`
14. Regression test suite + experiment manifests + final report

## Environment notes

- Windows 11, Git Bash; Python 3.14.7 in `.venv`; package manager: `uv`
- `gh` CLI authenticated as `sadatdaniel` → GitHub push works without user action
- WSL2 present but only `docker-desktop` distro exists; the Colab CLI (planned) needs a
  real Linux distro — will ask user before installing Ubuntu into WSL
- Local machine is weak: training happens on free Colab GPUs, not locally

## Decisions log

- Package name `project` kept exactly as the brief's example commands suggest
  (`python -m project.sources.inventory`, `python -m project.collect`).
- Registry normalization is deterministic (no timestamps) so the YAML diffs cleanly.
- Raw/normalized/curated data are git-ignored (privacy + size); manifests, reports,
  and metadata are committed.
- Dependency stack starts minimal (httpx, bs4/lxml, pyyaml, feedparser); ML deps
  (torch/transformers/trl/peft) will be added when training code lands, so local
  installs stay light.
