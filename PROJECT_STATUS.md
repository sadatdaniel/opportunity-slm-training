# Project Status

Single source of truth for build state. Update after every milestone.
Agent entry point: `AGENT_PICKUP.md`. Spec: `opportunity_intelligence_weekend_build_v3.md`
(private, git-ignored).

- **Current phase**: scale-up loop — dataset v4 frozen; corpus growing toward 10k
- **Blocking human actions**: none required right now (review queue optional)
- **Current commit**: see `git log -1`

## Snapshot (2026-09-26)

- **Corpus**: 4,670 canonical records, 19 productive sources (target ~10k;
  collection waves 1-5 done, wave 6+ = deeper quotas + weak-class targeting)
- **Annotation**: classify 4,256 usable / summarize 4,145+ usable — all
  collected waves labeled (multi-pass: Gemini primary → OmniRoute/OpenRouter
  second opinion → Experiential Labs + DeepSeek verification)
- **Verification**: 4,172 astra/DeepSeek verdicts; consensus = 3,321
  confirmed / 640 single-disagreement (gpt-6-luna tiebreak pending) /
  165 unverified (DeepSeek pass pending) / 4 split (human queue) / 80 gold
- **Datasets frozen**: classifier v1-v4, summarizer v1-v4
  (v4: classifier 1,924/240/241 + 1,279 unseen; summarizer 2,520/315/315 + 691)
- **Models**: classifier v0.2.0 released (84.3% acc / F1 0.733 / ECE 0.054);
  summarizer v0.1.0 released (partial, documented); summarizer v0.3.0
  trained on Colab with all three format fixes — eval pending
- **Tests**: 57 passing
- **Releases**: `classifier-v0.2.0`, `summarizer-v0.1.0` (GitHub)

## A/B queue (next Colab runs, one at a time)

1. Evaluate summarizer v0.3.0 (trained on v3, single-template + stable
   boundary fix). Model on the Colab VM at
   `models/summarizer/v0.3.0` — eval cell pattern in chat history/§Colab.
2. Summarizer A/B on dataset v4: `config_qwen06.yaml` (full-FT) and
   `config_minicpm_lora.yaml` (quality ceiling) — one command each via
   `colab_train_wsl.sh summarizer` after pointing the config.
3. Classifier retrain on dataset v4 (consensus-clean) — expect >84.3%.
4. Per-type temperature calibration (laya lesson) for both capabilities.

## Human actions required

- Optional: review queue `uv run streamlit run project/review.py` —
  ~45 summarize + ~33 classify flagged records (gpt-6-luna tiebreaks +
  split verdicts). Not blocking; flagged records stay out of training.

## In flight

- Wave-5+ annotate/verify chain (background) — then consensus re-run →
  dataset v4.1
- Summarizer v0.3.0 eval (user's Colab notebook, Cell 4)

## Colab state

- Session `oi-trainer`: a fresh T4 is created per training run via
  `colab_train_wsl.sh CAPABILITY` (capability is ARG 1 — env vars do not
  cross into WSL). Driver files hardcode the capability per file.
- Drive durability wired for the summarizer driver (mount → resume-from-
  checkpoint → `.complete` markers). Extend to the classifier driver.
- Known failure: WebSocket drops on network instability — the kernel often
  finishes anyway; reconnect + `colab_vm_probe.py` before relaunching.

## Ops lessons (binding — full detail in AGENT_PICKUP.md §0/§4 and git history)

- Rolling-24h provider budgets with safety margins; calendar-minute RPM
  windows; atomic slot reservation; exhaustion = ALL role slots dry
- DeepSeek: CONCURRENCY limits (2500 flash / 500 v4-pro), not RPM — 64
  workers fine; keller-project scripts are the reference implementation
- OpenRouter free tier: Nemotron-3.5-lightning degraded (11.8% JSON valid)
  — model choice must be verified by shootout, not assumed
- Z.ai = Coding Plan endpoint (`api/coding/paas/v4`); standard endpoint
  rejects subscription keys with "insufficient balance"
- `colab exec` 30s default timeout; fp32 on T4 is ~2× slower than bf16 —
  summarizer trains at 1,024 tokens for this reason
- Single-vs-double chat template application caused a full-model failure
  (v0.1.0 summarizer): train/inference prompt rendering must be identical —
  now shared via `training/summarizer/prompt.py` (raw mode, stable
  `TARGET OUTPUT:` boundary)

## Docker coexistence rules (binding)

Never delete/stop/rename/overwrite/prune Docker resources this project did
not create; never run `docker ... prune`; project resources are prefixed
`opportunity_slm_` (currently only the omniroute container). Containers are
disposable; never authoritative storage.

## Policy changes (traceable)

- 2026-09-25: robots.txt adherence disabled by user instruction for
  public-page feed discovery and collection; politeness retained
  (delays, cache, honest UA). Recorded in scripts/backup_repo.sh header.

## Remaining (ordered)

1. Summarizer v0.3.0 evaluation → release decision
2. gpt-6-luna tiebreak on 640 disagreements + DeepSeek pass on 165
3. Dataset v4.1 → classifier retrain (target: beat 84.3% with cleaner data)
4. Summarizer A/B: Qwen3-0.6B full-FT and MiniCPM5-2B LoRA on v4
5. Per-type temperature calibration; confidence-gated serving thresholds
6. Scale corpus to ~10k (waves 6-8); taxonomy v2 decision from confusion
   matrix; Noul training data from extraction facts
