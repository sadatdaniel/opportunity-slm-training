"""System-One batching benchmark (brief section 4B).

Benchmarks one state against 1/2/4/8/16 questions and reports total latency,
per-question effective latency, token accounting (honestly: this prototype
re-encodes the state per question, so state tokens processed scale with
question count), peak memory, and batched-versus-single equivalence.

Usage::

    python -m training.systemone.benchmark_batch \
        --model SupraLabs/Supra2-100M-Instruct --state-words 300 --repeats 3
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch

from training.common.experiment import PROJECT_ROOT
from training.systemone.engine import ChoiceQuestion, NoulQuestion, SystemOneEngine

REPORT_DIR = PROJECT_ROOT / "reports"
QUESTION_POOL = [
    ("deadline", NoulQuestion(
        instructions="Is an application deadline explicitly stated?",
        criteria={"true": "An explicit application deadline is stated.", "false": "No explicit deadline is stated."})),
    ("funded", NoulQuestion(
        instructions="Does the opportunity provide direct financial support?",
        criteria={"true": "Direct financial support is provided.", "false": "No direct financial support is stated."})),
    ("german", NoulQuestion(
        instructions="Is German proficiency mandatory?",
        criteria={"true": "German is mandatory.", "false": "German is not mandatory."})),
    ("under40", NoulQuestion(
        instructions="Must applicants be under 40 years old?",
        criteria={"true": "Applicants must be under 40.", "false": "No such age limit applies."})),
    ("nomination", NoulQuestion(
        instructions="Is nomination by an institution mandatory?",
        criteria={"true": "Nomination is mandatory.", "false": "Nomination is not required."})),
    ("category", ChoiceQuestion(
        instructions="Which type best describes this posting?",
        criteria={
            "scholarships": "Financial support for education.",
            "fellowships": "Structured professional or research program.",
            "internships": "Work experience placement.",
            "competitions": "Contest with prizes.",
        })),
    ("attendance", NoulQuestion(
        instructions="Is in-person attendance mandatory?",
        criteria={"true": "In-person attendance is mandatory.", "false": "In-person attendance is not required."})),
    ("letters", NoulQuestion(
        instructions="Are recommendation letters mandatory?",
        criteria={"true": "Recommendation letters are required.", "false": "Recommendation letters are not required."})),
]


def make_questions(n: int) -> dict:
    out = {}
    for i in range(n):
        name, question = QUESTION_POOL[i % len(QUESTION_POOL)]
        out[f"{name}_{i}"] = question
    return out


@torch.no_grad()
def benchmark(engine: SystemOneEngine, state: str, sizes: list[int], repeats: int) -> list[dict]:
    state_tokens = len(engine.tokenizer.encode(state))
    rows = []
    for size in sizes:
        questions = make_questions(size)
        times = []
        for _ in range(repeats):
            start = time.perf_counter()
            batched = engine.answer_batch(state, questions)
            times.append(time.perf_counter() - start)
        singles = {}
        start = time.perf_counter()
        for qid, question in questions.items():
            singles[qid] = (
                engine.answer_noul(state, question)
                if isinstance(question, NoulQuestion)
                else engine.answer_choice(state, question)
            )
        single_total = time.perf_counter() - start
        equivalent = all(
            abs((batched[qid].noul if hasattr(batched[qid], "noul") else batched[qid].confidence)
                - (s.noul if hasattr(s, "noul") else s.confidence)) < 1e-9
            for qid, s in singles.items()
        )
        peak_mem = (
            torch.cuda.max_memory_allocated() / 1e6
            if torch.cuda.is_available()
            else None
        )
        rows.append({
            "questions": size,
            "batched_total_latency_s": round(statistics.median(times), 3),
            "batched_per_question_ms": round(statistics.median(times) / size * 1000, 1),
            "single_total_latency_s": round(single_total, 3),
            "state_tokens": state_tokens,
            "state_tokens_processed": state_tokens * size,  # honest accounting: no KV reuse in v0
            "peak_memory_mb": round(peak_mem, 1) if peak_mem else None,
            "equivalent_to_single": equivalent,
            "speedup_vs_single_x": round(single_total / statistics.median(times), 2),
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="System-One batching benchmark")
    parser.add_argument("--model", default="SupraLabs/Supra2-100M-Instruct")
    parser.add_argument("--state-words", type=int, default=300)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--sizes", default="1,2,4,8,16")
    args = parser.parse_args(argv)

    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model)
    engine = SystemOneEngine(model, tokenizer, max_state_words=args.state_words)

    from project.freeze_corpus import PROJECT_ROOT as ROOT

    lines = (ROOT / "data" / "normalized" / "deduped.jsonl").read_text(encoding="utf-8").splitlines()
    import json

    state = json.loads(lines[0])["clean_text"]

    rows = benchmark(engine, state, [int(s) for s in args.sizes.split(",")], args.repeats)
    payload = {
        "model": args.model,
        "device": engine.device,
        "state_words": args.state_words,
        "limitation": "v0 prototype re-encodes the state per question; tokens processed scale with question count (no KV reuse yet)",
        "rows": rows,
        "benchmarked_at": datetime.now(timezone.utc).isoformat(),
    }
    REPORT_DIR.mkdir(exist_ok=True)
    out = REPORT_DIR / "systemone_batch_benchmark.json"
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(json.dumps(rows, indent=1))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
