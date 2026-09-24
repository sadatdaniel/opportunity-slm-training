# Project Status

Single source of truth for build state, so any future session or agent can
resume exactly where work stopped. Update after every milestone.

- **Specification**: `opportunity_intelligence_weekend_build.md` (private, git-ignored, never commit)
- **Current phase**: 1 — Source inventory
- **Blocking human actions**: none
- **Current commit**: see `git log -1` (updated at each milestone)

## Completed

- [x] Read full build brief and `100_academic_sources.md` (106 sources, JSON array)
- [x] Git hygiene: `.gitignore` created; build brief verified ignored before first commit
- [x] Initial project structure (packages: `project`, `collectors`, `training`)
- [x] Source registry normalizer: `100_academic_sources.md` → `sources/registry.yaml`
      (stable `source_id` slugs, derived `domain`, provenance preserved)
- [x] Polite fetching framework `collectors/base.py` (cache, per-host delay+jitter,
      Retry-After/backoff, robots.txt check, honest User-Agent)
- [x] Private GitHub repository `sadatdaniel/opportunity-slm-training` created and pushed
- [x] Source inventory probe (`python -m project.sources.inventory`) — WP REST/other API,
      RSS/Atom, robots.txt, response characteristics per source
- [x] Inventory report: `reports/source_inventory.md` + machine-readable `data/inventory.json`

## In progress

- (nothing currently running)

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
