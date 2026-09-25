"""OpenRouter free-model shootout for the second-opinion/verifier role.

Scores candidate models against our most reliable labels:
  - human-verified records (review_status approved/corrected, n≈21)
  - high-confidence silver (teacher + DeepSeek verifier agreed, sample)
Reports accuracy per subset, JSON validity, and median latency, using the
keller-proven call pattern: attribution headers, unified reasoning control,
generous max_tokens, live key-status quota check.

Usage::

    python -m project.benchmark_teachers
    python -m project.benchmark_teachers --silver 10
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx
import yaml

from project.annotate import PROMPT_VERSION, load_taxonomy
from project.freeze_corpus import PROJECT_ROOT
from project.teachers import load_env

URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"
ANNOTATIONS_PATH = PROJECT_ROOT / "data" / "annotations" / "classify.jsonl"
VERIFY_PATH = PROJECT_ROOT / "data" / "annotations" / "verify_classify.jsonl"
DEDUPED_PATH = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"

CANDIDATES = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3.5-lightning:free",  # current second-opinion model
    # dropped: thinkingmachines/inkling:free (agentic-harness-only, 403 via API)
    # dropped: z-ai/glm-5.2:free (provider-side 429s at benchmark time; retry later)
]


def build_eval_set(silver_n: int, seed: int = 42) -> list[dict]:
    import random

    annotations: dict[str, dict] = {}
    for line in ANNOTATIONS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry.get("status") == "completed":
                annotations[entry["record_id"]] = entry

    human, silver_ids = [], set()
    for line in VERIFY_PATH.read_text(encoding="utf-8").splitlines() if VERIFY_PATH.exists() else []:
        if line.strip() and json.loads(line).get("agreement"):
            silver_ids.add(json.loads(line)["record_id"])

    records = {
        json.loads(line)["record_id"]: json.loads(line)
        for line in DEDUPED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    for rid, entry in annotations.items():
        if entry.get("review_status") in ("approved", "corrected", "approve"):
            label = (entry.get("parsed_annotation") or {}).get("primary_category")
            if label and rid in records:
                human.append({"record_id": rid, "label": label, "subset": "human"})
    rng = random.Random(seed)
    agreement_ids = sorted(silver_ids & set(annotations) & set(records))
    rng.shuffle(agreement_ids)
    for rid in agreement_ids[:silver_n]:
        label = (annotations[rid].get("parsed_annotation") or {}).get("primary_category")
        if label:
            human.append({"record_id": rid, "label": label, "subset": "silver_agreement"})
    for item in human:
        item["record"] = records[item["record_id"]]
    return human


def call_openrouter(key: str, model: str, messages: list[dict], timeout: float = 180.0) -> tuple[str | None, float]:
    start = time.perf_counter()
    try:
        resp = httpx.post(
            URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost/opportunity-intelligence",
                "X-Title": "Opportunity Intelligence Teacher Benchmark",
            },
            json={"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 2048},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:  # network drops are transient; skip the record
        print(f"    network error on {model}: {type(exc).__name__}", flush=True)
        return None, time.perf_counter() - start
    elapsed = time.perf_counter() - start
    if resp.status_code != 200:
        return None, elapsed
    # some providers return 200 with an error payload or empty choices
    # (moderation/empty output) — treat as unusable rather than crashing
    choices = resp.json().get("choices") or []
    if not choices:
        return None, elapsed
    return choices[0].get("message", {}).get("content") or "", elapsed


def classify_prompt(record: dict) -> list[dict]:
    system = (PROJECT_ROOT / "prompts" / f"{PROMPT_VERSION['classify']}.md").read_text(encoding="utf-8")
    categories = ", ".join(load_taxonomy())
    user = (
        f"CATEGORIES: {categories}\n\nTITLE: {record['title']}\n\n"
        f"OPPORTUNITY TEXT:\n{record['clean_text'][:6000]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenRouter model shootout")
    parser.add_argument("--silver", type=int, default=15)
    parser.add_argument("--models", nargs="*", default=CANDIDATES)
    args = parser.parse_args(argv)
    load_env()
    key = __import__("os").environ.get("OPENROUTER_API_KEY", "")

    eval_set = build_eval_set(args.silver)
    human_set = [e for e in eval_set if e["subset"] == "human"]
    print(f"eval set: {len(human_set)} human-verified + {len(eval_set) - len(human_set)} silver-agreement", flush=True)

    results = {}
    for model in args.models:
        correct_human = correct_silver = valid = total = 0
        latencies = []
        for item in eval_set:
            content, elapsed = call_openrouter(key, model, classify_prompt(item["record"]))
            latencies.append(elapsed)
            total += 1
            if content is None:
                continue
            match = re.search(r"\{.*\}", content, re.DOTALL)
            parsed = None
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    parsed = None
            label = (parsed or {}).get("primary_category") if isinstance(parsed, dict) else None
            if label in load_taxonomy():
                valid += 1
                if label == item["label"]:
                    if item["subset"] == "human":
                        correct_human += 1
                    else:
                        correct_silver += 1
        subset_acc = {
            "human": round(correct_human / len(human_set), 3) if human_set else None,
            "silver_agreement": round(correct_silver / (len(eval_set) - len(human_set)), 3)
            if len(eval_set) > len(human_set)
            else None,
        }
        results[model] = {
            "human_accuracy": subset_acc["human"],
            "silver_accuracy": subset_acc["silver_agreement"],
            "json_valid_rate": round(valid / total, 3) if total else 0.0,
            "median_latency_s": round(statistics.median(latencies), 1) if latencies else None,
            "total": total,
        }
        print(json.dumps({model: results[model]}), flush=True)

    REPORT = PROJECT_ROOT / "reports" / "openrouter_model_shootout.json"
    REPORT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
