# Project Status

Single source of truth for build state. Update after every milestone.

- **Specification**: `opportunity_intelligence_weekend_build_v2.md` (private, git-ignored)
- **Current phase**: v2 step 5 — teacher annotation pilot (awaiting API keys)
- **Blocking human actions**: teacher API keys (see below)
- **Current commit**: see `git log -1`

## Human actions required

1. **Teacher API keys** — copy `.env.example` → `.env`, fill any subset of:
   `GEMINI_API_KEY` (+`GEMINI_API_KEY2..4` for the other Google projects),
   `OPENROUTER_API_KEY`, `ZAI_API_KEY`, or legacy `TEACHER_*`.
   Then run: `uv run python -m project.annotate --task classify --pilot`
2. (Later, for Colab CLI) WSL2 has only the docker-desktop distro; installing
   Ubuntu (`wsl --install Ubuntu`) requires user action. Must not block current work.

## v2 execution state (brief §39A order)

| step | status | artifact |
|---|---|---|
| 1. Freeze corpus v1 | done | `data/manifests/corpus_v1.yaml` (3,296 records, sha256) |
| 2. Supra tokenizer stats | done | `reports/token_stats.md` — 98% of prompt+target ≤1024 tok |
| 3. Taxonomy audit sample | done, awaiting human read | `reports/taxonomy_audit_sample.md` |
| 4. Imbalance report | done | `reports/imbalance_report.md` (starved: exchange_programs 0.2%, postdoc 0.1%; 46% of titles carry no type signal) |
| 5. Teacher annotation pilot | **blocked on keys** | `python -m project.annotate --task classify --pilot` |
| 6. classifier_dataset_v1 | pending pilot | `python -m project.build_dataset --task classify` |
| 7. First classifier experiment (Von vs Supra) | pending | Colab training workflow needed |
| 8. Model-driven collection | pending step 7 | HTML recipes for 54 html sources |
| 9. Summarizer pilot (300) | pending | `--task summarize --pilot 300` |

## Established state (from v1 build)

- Private repo `sadatdaniel/opportunity-slm-training`, pushed at every milestone
- 106 sources probed: 14 wp_rest / 7 rss / 54 html / 17 bad endpoints / 14 blocked
- corpus_v1: 4,281 raw → 3,335 normalized → 3,296 canonical from 16 sources
- taxonomy_v1: 12 categories + aliases (`config/taxonomy_v1.yaml`)
- collector framework, normalization, layered dedup, dataset builder with
  gold/silver/quarantine tiers, leakage-aware splits, unseen-source holdout
- multi-provider teacher pool (§17A/17B): gemini_1..4 primary slots,
  openrouter second opinion, zai adjudicator, legacy fallback; per-slot
  quota tracking with 85% safety margin, Retry-After/backoff, rotation,
  persisted state, resumable annotation, staleness fields

## Remaining after pilot

1. Human-review pilot annotations (review queue UI — Streamlit, brief §18)
2. `classifier_dataset_v1` (build_dataset skips stale/invalid annotations)
3. Colab/WSL training workflow; Von baseline; Supra classifier experiment
4. Field-level summarizer benchmark scaffolding (§22A) before summarizer pilot
5. FastAPI service (strict endpoints) → `Dockerfile.api` + compose service
6. Regression suite, experiment manifests, final report

## Docker coexistence rules (v2 brief §27 — binding)

- Never delete/stop/rename/overwrite/prune Docker resources this project did not create
- Never run `docker system prune` / `volume prune` / `network prune` / `image prune -a`
- All project resources are prefixed `opportunity_slm_` (compose project name
  `opportunity_slm`); currently only `Dockerfile.dev` + `docker-compose.yml` exist
- Docker Desktop's internal WSL distros are NOT the project's Linux environment

## Decisions log

- Package name `project` kept exactly as the briefs' example commands suggest
- Registry normalization deterministic; raw/normalized/curated data git-ignored;
  manifests, reports, metadata committed
- Annotation entries are append-only with full provenance; dataset building
  skips entries whose `prompt_version`/`taxonomy_version`/`input_hash` are stale
- `Dockerfile.api` deliberately deferred until the inference service exists
- Gemini daily-cap responses surface as 403 on the free tier: treated as
  rate-limit rotation signal, not a hard refusal
