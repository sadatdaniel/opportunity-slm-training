"""Human review queue for teacher annotations (build brief section 18).

A deliberately small Streamlit app. Shows source opportunity, teacher target,
classification, and flags; every correction is preserved alongside the
original teacher output. Nothing is silently overwritten:
``teacher_raw_response``/``parsed_annotation`` stay untouched, human edits go
to dedicated fields.

Usage::

    uv run streamlit run project/review.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from project.annotate import load_taxonomy
from project.freeze_corpus import PROJECT_ROOT

ANNOTATION_DIR = PROJECT_ROOT / "data" / "annotations"
NORMALIZED_PATH = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"

st.set_page_config(page_title="Opportunity Review", layout="wide")


@st.cache_data
def load_records() -> dict:
    records = {}
    if NORMALIZED_PATH.exists():
        for line in NORMALIZED_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                records[rec["record_id"]] = rec
    return records


def load_annotations(task: str) -> tuple[Path, list[dict]]:
    path = ANNOTATION_DIR / f"{task}.jsonl"
    if not path.exists():
        return path, []
    return path, [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_annotations(path: Path, entries: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def queue_sort_key(entry: dict) -> tuple:
    """Review-priority order: unresolved first, then by flag count."""
    status = entry.get("review_status")
    severity = {"rejected": 0, None: 1, "ambiguous": 2, "corrected": 3, "approved": 4}
    return (severity.get(status, 1), -len(entry.get("review_flags") or []))


def main() -> None:
    records = load_records()
    task = st.sidebar.selectbox("Task", ["classify", "summarize"])
    path, entries = load_annotations(task)
    if not entries:
        st.warning(f"No annotations at {path}. Run `python -m project.annotate --task {task} --pilot` first.")
        return

    counts: dict[str, int] = {}
    for e in entries:
        counts[e.get("review_status") or "pending"] = counts.get(e.get("review_status") or "pending", 0) + 1
    st.sidebar.metric("total", len(entries))
    st.sidebar.json(counts)

    filter_status = st.sidebar.selectbox("Filter", ["pending", "ambiguous", "approved", "corrected", "rejected", "all"])
    pool = [e for e in entries if filter_status == "all" or (e.get("review_status") or "pending") == filter_status]
    pool.sort(key=queue_sort_key)

    if not pool:
        st.success("Queue empty for this filter.")
        return
    index = st.sidebar.number_input("Record", min_value=1, max_value=len(pool), value=1)
    entry = pool[index - 1]
    record = records.get(entry["record_id"], {})
    parsed = entry.get("parsed_annotation") or {}

    st.title(f"Review: {task} ({index}/{len(pool)} in filter)")
    st.subheader(record.get("title", entry["record_id"]))
    st.caption(f"{record.get('source_id', '?')} · {record.get('canonical_url', '')}")

    with st.expander("SOURCE OPPORTUNITY", expanded=True):
        words = (record.get("clean_text") or "").split()
        st.text(" ".join(words[:900]) + (" …" if len(words) > 900 else ""))

    left, right = st.columns(2)
    with left:
        st.subheader("TEACHER TARGET")
        if task == "classify":
            categories = load_taxonomy()
            chosen = st.selectbox("primary_category", categories, index=categories.index(parsed.get("primary_category", categories[0])) if parsed.get("primary_category") in categories else 0)
            st.caption(f"secondary: {parsed.get('secondary_plausible_categories')} · ambiguity: {parsed.get('classification_ambiguity')}")
            st.caption(f"reason: {parsed.get('reason_for_label')}")
        else:
            edited_summary = st.text_area("summary target", parsed.get("summary", ""), height=360)
        st.caption(f"provider: {entry.get('teacher_provider_slot')} · {entry.get('teacher_model')} · {entry.get('teacher_timestamp')}")
    with right:
        st.subheader("FLAGS")
        st.write(entry.get("review_flags") or [])
        st.write(f"validation: {entry.get('validation_status')} · needs_human_review: {entry.get('needs_human_review')}")
        if entry.get("adjudication_suggestion"):
            st.info(f"adjudicator ({entry.get('adjudication_provider')}) suggests: {entry['adjudication_suggestion']}")

    st.subheader("ACTION")
    note = st.text_input("review note")
    action = st.radio(
        "decision",
        ["skip", "approve", "corrected", "reject", "mark ambiguous"],
        horizontal=True,
        label_visibility="collapsed",
    )
    if st.button("Save decision") and action != "skip":
        entry["original_teacher_parsed"] = entry.get("original_teacher_parsed") or entry.get("parsed_annotation")
        entry["review_status"] = action
        entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        entry["human_notes"] = note or entry.get("human_notes")
        if task == "classify":
            if action == "corrected" or (action == "approve" and parsed.get("primary_category") != chosen):
                entry["human_category"] = chosen
                entry["parsed_annotation"] = {**parsed, "primary_category": chosen}
        elif action == "corrected":
            entry["human_corrected_output"] = edited_summary
            entry["parsed_annotation"] = {**parsed, "summary": edited_summary}
        save_annotations(path, entries)
        st.cache_data.clear()
        st.rerun()


main()
