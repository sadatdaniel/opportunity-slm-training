"""Noul evaluation: binary-probability metrics (brief sections 4A, 23).

Evaluates any engine against a Noul item set (e.g. noul_prototype_v0):
Brier score, calibration bins, thresholded precision/recall/F1 across
thresholds, ROC-AUC / PR-AUC, and the empirical best-threshold table so
production thresholds come from held-out data, never assumption (brief 4A).

Usage::

    python -m training.noul.evaluate --model SupraLabs/Supra2-100M-Instruct \
        --items data/curated/noul_prototype_v0.jsonl --limit 60
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_fscore_support, roc_auc_score

from training.common.experiment import PROJECT_ROOT
from training.systemone.engine import NoulQuestion, SystemOneEngine

REPORT_DIR = PROJECT_ROOT / "reports"


def load_items(path: Path, limit: int | None) -> list[dict]:
    items = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return items if limit is None else items[:limit]


def evaluate(engine: SystemOneEngine, items: list[dict]) -> dict:
    predictions: list[float] = []
    targets: list[bool] = []
    failures: list[dict] = []
    for item in items:
        question = NoulQuestion(**item["question"])
        answer = engine.answer_noul(item["state"], question)
        predictions.append(answer.noul)
        targets.append(bool(item["target"]))
        if abs(answer.noul - 0.5) < 0.02:  # no separation at all
            failures.append({"item_id": item["item_id"], "noul": answer.noul, "case": item["case"]})

    y = np.array(targets, dtype=int)
    p = np.array(predictions)
    errors = np.abs(p - y)

    threshold_table = {}
    for threshold in (0.3, 0.4, 0.5, 0.6, 0.7):
        pred = (p >= threshold).astype(int)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y, pred, average="binary", zero_division=0
        )
        threshold_table[str(threshold)] = {
            "precision": round(float(precision), 3),
            "recall": round(float(recall), 3),
            "f1": round(float(f1), 3),
        }

    bins = []
    edges = np.linspace(0.0, 1.0, 11)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p > lo) & (p <= hi)
        if mask.sum():
            bins.append({
                "bin": [round(float(lo), 1), round(float(hi), 1)],
                "mean_predicted": round(float(p[mask].mean()), 3),
                "fraction_true": round(float(y[mask].mean()), 3),
                "count": int(mask.sum()),
            })

    ece = sum(
        b["count"] / len(p) * abs(b["mean_predicted"] - b["fraction_true"]) for b in bins
    )
    return {
        "n": len(items),
        "brier": round(float(((p - y) ** 2).mean()), 4),
        "roc_auc": round(float(roc_auc_score(y, p)), 3) if len(set(y)) > 1 else None,
        "pr_auc": round(float(average_precision_score(y, p)), 3) if len(set(y)) > 1 else None,
        "mean_absolute_error": round(float(errors.mean()), 3),
        "no_separation_rate": round(len(failures) / len(p), 3),
        "ece": round(float(ece), 3),
        "calibration_bins": bins,
        "threshold_table": threshold_table,
        "failures": failures[:10],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Noul binary decisions")
    parser.add_argument("--model", default="SupraLabs/Supra2-100M-Instruct")
    parser.add_argument("--items", default="data/curated/noul_prototype_v0.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--device", default=None)
    args = parser.parse_args(argv)

    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model)
    engine = SystemOneEngine(model, tokenizer, device=args.device)

    items = load_items(PROJECT_ROOT / args.items, args.limit)
    results = evaluate(engine, items)
    payload = {
        "model": args.model,
        "items_file": args.items,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "results": results,
    }
    REPORT_DIR.mkdir(exist_ok=True)
    out = REPORT_DIR / f"noul_eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items() if k != "calibration_bins"}, indent=1))
    print(f"full results -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
