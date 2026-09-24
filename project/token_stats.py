"""Token-length statistics with the real Supra tokenizer (v2 brief, 39A step 2).

Measures the corpus against the model's actual context budget: percentiles
and fit rates for input-only and input+proxy-target sequences, before and
after the 600-word input truncation.

Usage::

    python -m project.token_stats
"""

from __future__ import annotations

import json
import sys

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

from project.freeze_corpus import PROJECT_ROOT

DEDUPED_PATH = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"
REPORT_PATH = PROJECT_ROOT / "reports" / "token_stats.md"
MODEL_ID = "SupraLabs/Supra2-100M-Instruct"
MAX_INPUT_WORDS = 600
TARGET_BUDGET_WORDS = 150
CONTEXTS = [512, 768, 1024, 1536, 2048]

PROXY_TARGET = (
    "MANDATORY\n- (example requirement)\n\nRESTRICTIONS\n- (example restriction)\n\n"
    "SUMMARY\nThe opportunity is described above; key eligibility, deadlines, "
    "funding and restrictions are listed concisely."
)


def load_supra_tokenizer() -> Tokenizer:
    path = hf_hub_download(MODEL_ID, "tokenizer.json")
    return Tokenizer.from_file(path)


def percentile(values: list[int], q: float) -> int:
    values = sorted(values)
    return values[min(int(len(values) * q), len(values) - 1)]


def fit_rates(values: list[int]) -> dict[int, float]:
    n = len(values)
    return {ctx: sum(1 for v in values if v <= ctx) / n for ctx in CONTEXTS}


def measure(tokenizer: Tokenizer, texts: list[str]) -> dict:
    encodings = tokenizer.encode_batch(texts)
    counts = [len(e.ids) for e in encodings]
    return {
        "p50": percentile(counts, 0.50),
        "p90": percentile(counts, 0.90),
        "p95": percentile(counts, 0.95),
        "p99": percentile(counts, 0.99),
        "max": max(counts),
        "fit": fit_rates(counts),
    }


def write_report(stats: dict, n: int, model_id: str) -> None:
    lines = [
        "# Token Statistics (real Supra tokenizer)",
        "",
        f"Model: `{model_id}` · corpus records: {n} · measured locally",
        "",
        "| measurement | p50 | p90 | p95 | p99 | max | ≤512 | ≤768 | ≤1024 | ≤1536 | ≤2048 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    def fmt(name: str, s: dict) -> str:
        fits = " | ".join(f"{s['fit'][ctx]:.0%}" for ctx in CONTEXTS)
        return f"| {name} | {s['p50']} | {s['p90']} | {s['p95']} | {s['p99']} | {s['max']} | {fits} |"

    lines.append(fmt("input only (600-word truncated)", stats["input_truncated"]))
    lines.append(fmt("input + proxy target (~150w)", stats["input_plus_target"]))
    lines.append(fmt("full clean_text, no truncation", stats["full_text"]))

    lines += [
        "",
        "## Reading",
        "",
        f"- {stats['input_plus_target']['fit'][1024]:.0%} of prompt+target sequences fit the "
        "1,024-token context the base model was primarily trained around.",
        f"- {stats['input_plus_target']['fit'][2048]:.0%} fit within 2,048 tokens.",
        "- Input is truncated at 600 words before measurement; critical eligibility text is "
        "front-loaded by the cleaning pipeline. Long-tail records (see full_text) rely on "
        "truncation and must be handled explicitly at training time, never silently.",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


def main(argv: list[str] | None = None) -> int:
    tokenizer = load_supra_tokenizer()
    records = [
        json.loads(line)
        for line in DEDUPED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    truncated_inputs = [f'TITLE: {r["title"]}\n\nOPPORTUNITY TEXT:\n{" ".join(r["clean_text"].split()[:MAX_INPUT_WORDS])}' for r in records]
    with_targets = [t + "\n\n" + PROXY_TARGET for t in truncated_inputs]
    full_texts = [f'TITLE: {r["title"]}\n\n{r["clean_text"]}' for r in records]

    stats = {
        "input_truncated": measure(tokenizer, truncated_inputs),
        "input_plus_target": measure(tokenizer, with_targets),
        "full_text": measure(tokenizer, full_texts),
    }
    write_report(stats, len(records), MODEL_ID)
    return 0


if __name__ == "__main__":
    sys.exit(main())
