"""Evaluate the classifier on frozen splits: trained head vs zero-shot baseline.

Reports accuracy, macro F1, per-class metrics, confusion matrix, calibration
(ECE/Brier, temperature scaling fit on validation), and latency — for both
the fine-tuned artifact and the untouched base model used as a zero-shot
SystemOne choice-scoring baseline (brief sections 22, 23, 39A step 7).

Usage::

    python -m training.classifier.evaluate                       # v0.1.0 vs base
    python -m training.classifier.evaluate --model models/classifier/v0.1.0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

from training.common.datasets import load_split, load_taxonomy_categories
from training.common.experiment import PROJECT_ROOT
from training.common.metrics import (
    classification_metrics,
    fit_temperature,
)

DEFAULT_MODEL = PROJECT_ROOT / "models" / "classifier" / "v0.1.0"
BASE_MODEL = "SupraLabs/Supra2-100M-Instruct"
REPORT_DIR = PROJECT_ROOT / "reports"
MAX_LENGTH = 512


def predict_trained(model_path: Path, texts: list[str], labels: list[str], device: str) -> tuple[np.ndarray, np.ndarray, float]:
    """One forward pass per record: returns (probabilities, logits, median ms)."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path)).to(device).eval()
    probs, logits_all, latencies = [], [], []
    with torch.no_grad():
        for text in texts:
            enc = tokenizer(text, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
            t0 = time.perf_counter()
            logits = model(**enc).logits[0]
            latencies.append((time.perf_counter() - t0) * 1000)
            logits_all.append(logits.float().tolist())
            probs.append(torch.softmax(logits.float(), dim=-1).tolist())
    return np.array(probs), np.array(logits_all), float(np.median(latencies))


def predict_zero_shot(base_model: str, texts: list[str], categories: list[str], device: str, limit: int | None) -> tuple[np.ndarray, float]:
    """Zero-shot SystemOne baseline: softmax over per-category criterion scores."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from training.systemone.engine import ChoiceQuestion, SystemOneEngine

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(base_model)
    engine = SystemOneEngine(model, tokenizer, device=device, max_length=MAX_LENGTH)
    question = ChoiceQuestion(
        instructions="Which opportunity category best describes this posting?",
        criteria={
            c: f"This posting is primarily a {c.replace('_', ' ')} opportunity." for c in categories
        },
    )
    rows = texts[: limit or len(texts)]
    probs, latencies = [], []
    for text in rows:
        start = time.perf_counter()
        answer = engine.answer_choice(text, question)
        latencies.append((time.perf_counter() - start) * 1000)
        probs.append([answer.probabilities[c] for c in categories])
    return np.array(probs), float(np.median(latencies)) if latencies else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classifier evaluation on frozen splits")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument("--zero-shot-limit", type=int, default=None, help="cap zero-shot records (CPU is slow)")
    parser.add_argument("--device", default=None)
    args = parser.parse_args(argv)

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    categories = load_taxonomy_categories()
    test = load_split("classifier", args.dataset_version, "test")
    validation = load_split("classifier", args.dataset_version, "validation")
    y_test = [r["target"] for r in test.examples]
    texts = [r["input"] for r in test.examples]

    results: dict = {"evaluated_at": datetime.now(UTC).isoformat(), "device": device,
                     "test_size": len(test.examples), "taxonomy": "taxonomy_v1"}

    # -- trained classifier ---------------------------------------------------
    probs, test_logits, latency = predict_trained(Path(args.model), texts, categories, device)
    preds = [categories[i] for i in probs.argmax(axis=1)]
    results["trained"] = classification_metrics(y_test, preds, probs, categories)
    results["trained"]["median_latency_ms"] = round(latency, 1)

    # temperature scaling fitted on validation logits, applied to test logits
    _, val_logits, _ = predict_trained(Path(args.model), [r["input"] for r in validation.examples], categories, device)
    temperature = fit_temperature(val_logits, [r["target"] for r in validation.examples], categories)
    results["trained"]["temperature"] = round(temperature, 4)
    calibrated = test_logits / temperature
    calibrated = np.exp(calibrated - calibrated.max(axis=1, keepdims=True))
    calibrated /= calibrated.sum(axis=1, keepdims=True)
    results["trained"]["calibrated_metrics"] = classification_metrics(
        y_test, [categories[i] for i in calibrated.argmax(axis=1)], calibrated, categories
    )["calibration"]

    # -- zero-shot base-model baseline ---------------------------------------
    probs_zs, latency_zs = predict_zero_shot(BASE_MODEL, texts, categories, device, args.zero_shot_limit)
    y_zs = y_test[: len(probs_zs)]
    preds_zs = [categories[i] for i in probs_zs.argmax(axis=1)]
    results["zero_shot_baseline"] = classification_metrics(y_zs, preds_zs, probs_zs, categories)
    results["zero_shot_baseline"]["median_latency_ms"] = round(latency_zs, 1)

    REPORT_DIR.mkdir(exist_ok=True)
    out = REPORT_DIR / f"classifier_eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")

    summary = {
        "trained": {k: results["trained"][k] for k in ("accuracy", "macro_f1", "median_latency_ms")},
        "trained_calibration": {k: results["trained"]["calibration"][k] for k in ("ece", "brier")},
        "trained_calibrated_ece": results["trained"]["calibrated_metrics"]["ece"],
        "temperature": results["trained"]["temperature"],
        "zero_shot": {k: results["zero_shot_baseline"][k] for k in ("accuracy", "macro_f1", "median_latency_ms")},
    }
    print(json.dumps(summary, indent=1))
    print(f"full results -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
