# Evaluation Methodology

Living document (brief 24A/37). One evaluation report per experiment under
`experiments/` and machine-readable results under `reports/`.

## Principles

- The frozen test set is touched once per model release; tuning happens on
  validation only.
- Every trained model is compared against the untouched base model on the
  same frozen data (before/after is the core claim, brief 22A).
- Negative results are reported, never hidden.

## Classifier / Choice evaluation

- Metrics: accuracy, macro F1, per-class precision/recall/F1, confusion
  matrix, class distribution (`training.common.metrics`).
- Confidence analysis (brief 4C): report `top_probability`,
  `top1_top2_margin`, entropy, and the production `confidence` definition
  (TypeSafe/Von normalized formula `(n*p_max-1)/(n-1)`, chosen over the raw
  margin because it stays anchored at chance level for n>2; revisit
  empirically with accuracy-by-confidence-bin and coverage-accuracy curves).
- Calibration: ECE (10 equal-width bins on top-1 probability), Brier score
  over the full distribution, temperature scaling fitted on validation;
  raw and calibrated probabilities both reported.
- Baselines: the untouched base model (random head) and, for comparison,
  the SystemOne zero-shot criterion scoring path.
- Latency/throughput: single-record median + p95 via
  `training.common.metrics.measure_latency`; memory on CUDA.

## Noul evaluation

- Probabilistic binary metrics (brief 23): Brier score, ECE over P(true),
  ROC-AUC, PR-AUC, mean absolute error, no-separation rate.
- Threshold tables (0.3…0.7) reporting precision/recall/F1 so the production
  threshold comes from held-out data — 0.5 is not assumed optimal (brief 4A).
- Sets: `data/curated/noul_prototype_v0.jsonl` (derived labels, protocol
  mechanics only) now; reviewed extraction-based sets later.

## System-One batching evaluation

- Invariant: batched answers must equal single answers exactly
  (structural in v0 — same scoring path; regression-tested in
  `tests/test_systemone.py`).
- Benchmark (`training.systemone.benchmark_batch`): 1/2/4/8/16 questions,
  total + per-question latency, state tokens processed (reported honestly:
  v0 re-encodes the state per question — no KV reuse; measured, not claimed
  away), peak memory, speedup vs single.

## Summarizer evaluation

- Field-level benchmark (brief 22A) once the frozen human-verified fact set
  exists: deadline exact/status/multiple accuracy, age/nationality/residency
  restriction recall, mandatory-condition precision/recall,
  preferred→mandatory error rate, numeric-condition accuracy, education/
  experience/language/target-group accuracy, funding preservation,
  hallucinated-fact rate, ≤150-word compliance.
- Lexical metrics (ROUGE) reported as secondary only.
- Every release compared against the untouched base model on the same frozen
  benchmark.

## Regression gates (brief 34)

A new model version is tested against the original frozen test set, the
latest frozen test set, hand-curated difficult cases, and known past
failures. A version that regresses seriously on any of these is not promoted
even if aggregate metrics improve.
