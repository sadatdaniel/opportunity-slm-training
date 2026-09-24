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
            current = parsed.get("primary_category", categories[0])
            primary = st.selectbox(
                "primary_category",
                categories,
                index=categories.index(current) if current in categories else 0,
            )
            secondary_default = [
                s for s in (parsed.get("secondary_plausible_categories") or [])
                if s in categories and s != primary
            ]
            secondary = st.multiselect(
                "secondary_plausible_categories",
                [c for c in categories if c != primary],
                default=secondary_default,
                help="Dispute or clear the teacher's secondary guesses here.",
            )
            ambiguity = st.number_input(
                "classification_ambiguity",
                min_value=0.0, max_value=1.0,
                value=float(parsed.get("classification_ambiguity") or 0.0),
                step=0.05,
            )
            reason = st.text_area("reason_for_label", parsed.get("reason_for_label", ""))
            st.caption(f"provider: {entry.get('teacher_provider_slot')} · {entry.get('teacher_model')} · {entry.get('teacher_timestamp')}")
        else:
            edited_summary = st.text_area("summary target", parsed.get("summary", ""), height=360)
    with right:
        st.subheader("FLAGS")
        st.write(entry.get("review_flags") or [])
        st.write(f"validation: {entry.get('validation_status')} · needs_human_review: {entry.get('needs_human_review')}")
        if entry.get("adjudication_suggestion"):
            st.info(f"adjudicator ({entry.get('adjudication_provider')}) suggests: {entry['adjudication_suggestion']}")

    st.subheader("ACTION")
    st.caption("Any field you change above is saved as a human correction "
               "(the teacher's original output stays preserved in original_teacher_parsed).")
    note = st.text_input("review note")
    action = st.radio(
        "decision",
        ["skip", "approved", "corrected", "reject", "mark ambiguous"],
        horizontal=True,
        label_visibility="collapsed",
    )
    if st.button("Save decision") and action != "skip":
        entry["original_teacher_parsed"] = entry.get("original_teacher_parsed") or entry.get("parsed_annotation")
        entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        entry["human_notes"] = note or entry.get("human_notes")

        changed: list[str] = []
        if task == "classify":
            new_parsed = dict(parsed)
            if primary != parsed.get("primary_category"):
                new_parsed["primary_category"] = primary
                changed.append("primary_category")
            if sorted(secondary) != sorted(parsed.get("secondary_plausible_categories") or []):
                new_parsed["secondary_plausible_categories"] = secondary
                changed.append("secondary_plausible_categories")
            if abs(float(ambiguity) - float(parsed.get("classification_ambiguity") or 0)) > 1e-9:
                new_parsed["classification_ambiguity"] = float(ambiguity)
                changed.append("classification_ambiguity")
            if reason and reason != (parsed.get("reason_for_label") or ""):
                new_parsed["reason_for_label"] = reason
                changed.append("reason_for_label")
            entry["parsed_annotation"] = new_parsed
            entry["human_category"] = primary
            if changed:
                entry["human_edited_fields"] = sorted(set(entry.get("human_edited_fields") or []) | set(changed))
        elif task == "summarize" and action == "corrected":
            entry["human_corrected_output"] = edited_summary
            entry["parsed_annotation"] = {**parsed, "summary": edited_summary}

        # a human decision resolves the review flag; only explicit ambiguity/reject keep it
        entry["review_status"] = "corrected" if (action == "approved" and changed) else action
        entry["needs_human_review"] = action in ("mark ambiguous", "reject")
        save_annotations(path, entries)
        st.cache_data.clear()
        st.rerun()


main()
