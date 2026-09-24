"""Teacher annotation pipeline (build brief sections 15-17).

Calls a provider-configurable teacher model to produce summarization and
classification annotations for curated records. Teacher output is NOT ground
truth: every annotation carries review metadata so the human-review queue can
prioritize ambiguous cases.

Secrets come from environment variables (or a .env file):
    TEACHER_BASE_URL   e.g. https://api.openai.com/v1  (OpenAI-compatible chat API)
    TEACHER_API_KEY
    TEACHER_MODEL      e.g. gpt-4.1-mini

Usage::

    python -m project.annotate --task summarize --limit 100
    python -m project.annotate --task classify
    python -m project.annotate --task classify --input data/curated/review_batch.jsonl

Output appends to ``data/annotations/<task>.jsonl``; re-runs skip records that
already have an annotation (resumable, cheap).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"
TAXONOMY_CONFIG = PROJECT_ROOT / "config" / "taxonomy_v1.yaml"
ANNOTATION_DIR = PROJECT_ROOT / "data" / "annotations"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

PROMPT_VERSION = {"summarize": "summarizer_v1", "classify": "classifier_v1"}
MAX_INPUT_WORDS = 600  # brief section 3: input budget for the summarizer task


def load_env(dotenv: Path = PROJECT_ROOT / ".env") -> None:
    if not dotenv.exists():
        return
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def teacher_config() -> dict:
    config = {
        "base_url": os.environ.get("TEACHER_BASE_URL", "").rstrip("/"),
        "api_key": os.environ.get("TEACHER_API_KEY", ""),
        "model": os.environ.get("TEACHER_MODEL", ""),
    }
    missing = [k for k, v in config.items() if not v]
    if missing:
        print(
            "Teacher model not configured. Copy .env.example to .env and fill in:\n"
            "  TEACHER_BASE_URL (OpenAI-compatible chat endpoint)\n"
            "  TEACHER_API_KEY\n"
            "  TEACHER_MODEL\n"
            f"missing: {', '.join(missing)}"
        )
        raise SystemExit(1)
    return config


def load_taxonomy() -> list[str]:
    if not TAXONOMY_CONFIG.exists():
        print(f"missing {TAXONOMY_CONFIG} — author it from reports/proposed_categories.md first")
        raise SystemExit(1)
    return list(yaml.safe_load(TAXONOMY_CONFIG.read_text(encoding="utf-8"))["categories"])


def build_messages(task: str, record: dict) -> list[dict]:
    system = (PROMPTS_DIR / f"{PROMPT_VERSION[task]}.md").read_text(encoding="utf-8")
    text = record["clean_text"]
    if task == "summarize":
        # Truncate at the word level; critical conditions live near the start.
        words = text.split()
        truncated = " ".join(words[:MAX_INPUT_WORDS])
        user = f'TITLE: {record["title"]}\n\nOPPORTUNITY TEXT:\n{truncated}'
    else:
        categories = ", ".join(load_taxonomy())
        user = (
            f'CATEGORIES: {categories}\n\nTITLE: {record["title"]}\n\n'
            f"OPPORTUNITY TEXT:\n{text[:6000]}"
        )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_teacher(config: dict, messages: list[dict]) -> str:
    resp = httpx.post(
        f"{config['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {config['api_key']}"},
        json={"model": config["model"], "messages": messages, "temperature": 0.1},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def parse_annotation(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def annotate(task: str, input_path: Path, limit: int | None) -> None:
    config = teacher_config()
    records = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    out_path = ANNOTATION_DIR / f"{task}.jsonl"
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if out_path.exists():
        done = {
            json.loads(line)["record_id"]
            for line in out_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    written = 0
    with out_path.open("a", encoding="utf-8") as out:
        for record in records:
            if limit is not None and written >= limit:
                break
            if record["record_id"] in done:
                continue
            raw = call_teacher(config, build_messages(task, record))
            parsed = parse_annotation(raw)
            entry = {
                "record_id": record["record_id"],
                "source_id": record["source_id"],
                "title": record["title"],
                "canonical_url": record["canonical_url"],
                "teacher_provider": "openai_compatible",
                "teacher_model": config["model"],
                "teacher_prompt_version": PROMPT_VERSION[task],
                "teacher_timestamp": datetime.now(timezone.utc).isoformat(),
                "teacher_raw_response": raw,
                "parsed_annotation": parsed,  # None -> quarantined by the review queue
            }
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            out.flush()
            written += 1
            if written % 25 == 0:
                print(f"  {task}: {written} annotated", flush=True)
            time.sleep(0.5)  # ponytail: fixed delay; add adaptive backoff if the API rate-limits
    print(f"annotated {written} new records -> {out_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Teacher annotation")
    parser.add_argument("--task", choices=["summarize", "classify"], required=True)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    load_env()
    annotate(args.task, args.input, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
