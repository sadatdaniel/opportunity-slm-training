"""Metrics: classification, calibration, and latency (brief sections 5, 22, 23)."""

from __future__ import annotations

import time

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support


def classification_metrics(y_true: list[str], y_pred: list[str], probabilities: np.ndarray | None, labels: list[str]) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "per_class": {
            label: {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, label in enumerate(labels)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "class_distribution": {label: int((np.array(y_true) == label).sum()) for label in labels},
    }
    if probabilities is not None:
        metrics["calibration"] = calibration_metrics(y_true, probabilities, labels)
    return metrics


def top1_probabilities(probabilities: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(predicted class index, top-1 probability) per row."""
    top = probabilities.argmax(axis=1)
    return top, probabilities[np.arange(len(top)), top]


def calibration_metrics(y_true: list[str], probabilities: np.ndarray, labels: list[str], n_bins: int = 10) -> dict:
    label_index = {label: i for i, label in enumerate(labels)}
    y_idx = np.array([label_index[y] for y in y_true])
    top, top_prob = top1_probabilities(probabilities)
    correct = (top == y_idx).astype(float)

    # Expected Calibration Error over the top-1 probability (equal-width bins)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    reliability = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (top_prob > lo) & (top_prob <= hi)
        if mask.sum() == 0:
            continue
        confidence, accuracy = float(top_prob[mask].mean()), float(correct[mask].mean())
        ece += mask.mean() * abs(confidence - accuracy)
        reliability.append({"bin": [float(lo), float(hi)], "confidence": confidence, "accuracy": accuracy, "count": int(mask.sum())})

    # Brier score over the full probability vector
    one_hot = np.eye(len(labels))[y_idx]
    brier = float(((probabilities - one_hot) ** 2).sum(axis=1).mean())

    sorted_probs = np.sort(probabilities, axis=1)
    margin = top_prob - sorted_probs[:, -2]

    return {
        "ece": float(ece),
        "brier": brier,
        "mean_top1_probability": float(top_prob.mean()),
        "mean_top1_margin": float(margin.mean()),
        "reliability_diagram": reliability,
    }


def fit_temperature(logits: np.ndarray, y_true: list[str], labels: list[str]) -> float:
    """Temperature scaling fit on validation logits (Guo et al. 2017)."""
    from scipy.optimize import minimize_scalar

    label_index = {label: i for i, label in enumerate(labels)}
    y_idx = np.array([label_index[y] for y in y_true])

    def nll(temperature: float) -> float:
        scaled = logits / max(temperature, 1e-6)
        scaled -= scaled.max(axis=1, keepdims=True)
        log_probs = scaled - np.log(np.exp(scaled).sum(axis=1, keepdims=True))
        return float(-log_probs[np.arange(len(y_idx)), y_idx].mean())

    result = minimize_scalar(nll, bounds=(0.05, 10.0), method="bounded")
    return float(result.x)


def measure_latency(predict_one, n: int = 50, warmup: int = 5) -> dict:
    """Median/p95 per-record latency in milliseconds for predict_one()."""
    for _ in range(warmup):
        predict_one()
    timings = []
    for _ in range(n):
        start = time.perf_counter()
        predict_one()
        timings.append((time.perf_counter() - start) * 1000)
    timings.sort()
    return {"median_ms": timings[len(timings) // 2], "p95_ms": timings[int(len(timings) * 0.95)]}
