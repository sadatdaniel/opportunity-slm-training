"""Evaluate the summarizer on the frozen test split (brief sections 22, 22A-lite).

Generates summaries with the fine-tuned model and the untouched base model,
and reports: <=150-word compliance, section-format compliance, ROUGE-L against
teacher targets, and latency. The full field-level benchmark (22A) applies
once the human-verified fact set exists.

Usage::

    python -m training.summarizer.evaluate --model models/summarizer/v0.1.0
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch

from training.common.datasets import load_split
from training.common.experiment import PROJECT_ROOT
from training.summarizer.prompt import build_raw_prompt

REPORT_DIR = PROJECT_ROOT / "reports"
BASE_MODEL = "SupraLabs/Supra2-100M-Instruct"
SECTIONS = ["DEADLINE", "MANDATORY", "RESTRICTIONS", "TARGET GROUP", "FUNDING", "APPLICATION", "SUMMARY"]


def rouge_l(pred: str, ref: str) -> float:
    """Sentence-level ROUGE-L F1 via LCS on word tokens."""
    a, b = pred.split(), ref.split()
    if not a or not b:
        return 0.0
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            dp[i][j] = dp[i - 1][j - 1] + 1 if a[i - 1] == b[j - 1] else max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[-1][-1]
    if lcs == 0:
        return 0.0
    return 2 * lcs / (len(a) + len(b))


def section_compliance(text: str) -> float:
    if not text.strip():
        return 0.0
    present = sum(1 for s in SECTIONS if s in text.upper())
    has_bullets = "-" in text
    return min(1.0, present / 3) * (1.0 if has_bullets else 0.5)


def generate(model, tokenizer, prompts: list[str], device: str, max_new_tokens: int = 220) -> list[str]:
    outputs = []
    for prompt in prompts:
        enc = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1536).to(device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                 pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
        text = tokenizer.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        outputs.append(text.strip())
    return outputs


def summarize_results(texts: list[str], refs: list[str]) -> dict:
    words = [len(t.split()) for t in texts]
    rouge = [rouge_l(t, r) for t, r in zip(texts, refs)]
    return {
        "n": len(texts),
        "word_limit_150_compliance": round(sum(1 for w in words if 0 < w <= 150) / len(words), 3),
        "word_count_p50": sorted(words)[len(words) // 2],
        "word_count_max": max(words),
        "empty_rate": round(sum(1 for t in texts if not t.strip()) / len(words), 3),
        "section_format_mean": round(statistics.mean(section_compliance(t) for t in texts), 3),
        "rouge_l_mean": round(statistics.mean(rouge), 3),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the summarizer")
    parser.add_argument("--model", default="models/summarizer/v0.1.0")
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--base-limit", type=int, default=20, help="base-model comparison subset (CPU is slow)")
    parser.add_argument("--device", default=None)
    args = parser.parse_args(argv)

    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    test = load_split("summarizer", args.dataset_version, "test")
    prompts = [build_raw_prompt(r["input"]) for r in test.examples]
    refs = [r["target"] for r in test.examples]
    results: dict = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "device": device,
        "model": args.model,
        "test_size": len(test.examples),
    }

    model_path = args.model if Path(args.model).exists() else PROJECT_ROOT / args.model
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(str(model_path)).to(device).eval()
    start = time.perf_counter()
    texts = generate(model, tokenizer, prompts, device)
    results["trained"] = summarize_results(texts, refs)
    results["trained"]["median_latency_ms"] = round((time.perf_counter() - start) / len(prompts) * 1000, 1)
    (REPORT_DIR / f"summaries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl").write_text(
        "\n".join(json.dumps({"reference": r, "generated": t}, ensure_ascii=False) for t, r in zip(texts, refs)),
        encoding="utf-8",
    )

    # untouched base model comparison on a subset (CPU-friendly)
    base_tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if base_tokenizer.pad_token is None:
        base_tokenizer.pad_token = base_tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL).to(device).eval()
    n = min(args.base_limit, len(prompts))
    start = time.perf_counter()
    base_texts = generate(base, base_tokenizer, prompts[:n], device, max_new_tokens=220)
    results["base_untouched"] = summarize_results(base_texts, refs[:n])
    results["base_untouched"]["median_latency_ms"] = round((time.perf_counter() - start) / n * 1000, 1)

    REPORT_DIR.mkdir(exist_ok=True)
    out = REPORT_DIR / f"summarizer_eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps({"trained": results["trained"], "base_untouched": results["base_untouched"]}, indent=1))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
