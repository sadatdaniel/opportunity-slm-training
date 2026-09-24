# Project Status

Single source of truth for build state. Update after every milestone.

- **Specification**: `opportunity_intelligence_weekend_build_v3.md` (private, git-ignored)
- **Current phase**: v3 step 7B — System-One/Noul prototype built; classifier dataset gate on human review
- **Blocking human actions**: review the 15 flagged pilot records (Streamlit queue ready)
- **Current commit**: see `git log -1`

## Human actions required

1. **Human review of pilot annotations** (brief step 6 gate):
   `uv run streamlit run project/review.py` — 15 flagged records (ambiguity +
   adjudicator disagreements) need approve/correct/reject decisions; a ~20-record
   spot check of unflagged silver labels is recommended before full-corpus annotation.
2. (Later, for the Colab CLI path) install an Ubuntu WSL distro — user action;
   the browser-notebook Colab path works today without it.

## v3 execution state (brief §39A order)

| step | status | artifact |
|---|---|---|
| 1. Freeze corpus v1 | done | `data/manifests/corpus_v1.yaml` (3,296 records, sha256) |
| 2. Supra tokenizer stats | done | `reports/token_stats.md` — 98% ≤1024 tok |
| 3. Taxonomy audit sample | done | `reports/taxonomy_audit_sample.md` |
| 4. Imbalance report | done | `reports/imbalance_report.md` |
| 5. Teacher annotation pilot | **done** | 194 records, 179 valid, 15 review; `reports/pilot_report.md` |
| 6. classifier_dataset_v1 | **blocked on human review** | `python -m project.build_dataset --task classify` |
| 7. First classifier experiment | ready after step 6 | `training/classifier/train.py` (+Von-style zero-shot comparison) |
| 7B. Noul + parallel questions | **prototype done** | see below |
| 9. Summarizer pilot (300) | pending | `--task summarize --pilot 300` |

## System-One / Noul state (v3 brief 4A/4B/4C)

- `training/systemone/engine.py`: model-agnostic decision layer; Noul
  (P(true) via criterion softmax) and Choice (distribution over criteria).
  Non-autoregressive, typed output, no prose possible.
- Choice confidence uses the source-verified TypeSafe/Von formula
  `(n·p_max−1)/(n−1)` (Von README's margin claim is n=2-only; research in
  session logs); margin + entropy exposed separately. No Jev parity claimed.
- Batch invariance: batched answers == single answers exactly
  (structural + regression-tested); API/protocol tests cover injection safety.
- `training/systemone/benchmark_batch.py`: honest accounting — v0 re-encodes
  the state per question (no KV reuse); measured, documented in the report.
- `project/build_noul_set.py` + `config/noul_families.yaml`: 230-item
  prototype set (derived labels, protocol mechanics only — not final truth).
- `training/noul/evaluate.py`: Brier/ECE/ROC-AUC/PR-AUC + threshold tables
  (production threshold from data, never assumed 0.5).
- `service/main.py`: FastAPI with /health, /version, /v1/capabilities,
  /v1/summarize, /v1/categorize, /v1/noul, /v1/systemone (registry-driven
  model swap: base ↔ trained artifacts, `config/task_registry.yaml`).
- Colab: `colab/colab_train.ipynb` + `docs/colab_workflow.md` (durable
  Drive checkpoints, `.complete` markers, resume from manifest commit).
- Methodology: `docs/training_methodology.md`, `docs/evaluation_methodology.md`.

## Established state (v1/v2 build)

- Private repo `sadatdaniel/opportunity-slm-training`; corpus_v1 frozen
  (3,296 canonical records, 16 sources); 106 sources probed; 39 recipes
- Multi-provider teacher pool (gemini_1..4 / openrouter / zai-coding-plan /
  legacy) with quota state, rotation, resumable annotation, staleness fields
- Human review queue (`project/review.py`) preserving teacher output
- 48 tests passing (unit + parser + pipeline + systemone + API)

## Remaining

1. **Human review** (15 flagged + 20 spot check) → `classifier_dataset_v1`
2. First classifier experiment: trained Supra vs zero-shot SystemOne baseline
   on the frozen test split; calibration report
3. Summarizer pilot (300, brief step 9) + field-level benchmark scaffold (§22A)
4. Full-corpus classification annotation (after review gate)
5. Noul training data from the reviewed extraction pass (brief 4A cases)
6. Colab smoke-interruption resume test (brief 24A acceptance test)
7. Dockerfile.api + compose api service; regression suite; final report

## Docker coexistence rules (binding, brief 27)

Never delete/stop/rename/overwrite/prune Docker resources this project did
not create; never run `docker ... prune`; all project resources prefixed
`opportunity_slm_`; containers are disposable, never authoritative storage.

## Decisions log

- Package `project` per brief command names; deterministic registry; raw data
  git-ignored, manifests/reports/metadata committed
- Annotation entries append-only with provenance; dataset builds skip stale
  entries (prompt/taxonomy/input-hash mismatch)
- Choice confidence: TypeSafe/Von-shipped normalized formula; margin kept as
  separate field; empirical choice documented in evaluation_methodology.md
- Z.ai uses the Coding Plan endpoint (`api/coding/paas/v4`) — the standard
  endpoint rejects the subscription key; no-balance slots auto-disable per run
- Gemini daily caps surface as 403: treated as rate-limit rotation, not refusal
- `Dockerfile.api` lands with the first deployable trained artifact
