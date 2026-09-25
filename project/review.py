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
from datetime import UTC, datetime
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


@st.cache_data
def load_verification() -> dict:
    """record_id -> verifier outcome for records the independent verifier disputed."""
    path = ANNOTATION_DIR / "verify_classify.jsonl"
    disputed: dict[str, dict] = {}
    if not path.exists():
        return disputed
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("agreement") is False:
                disputed[row["record_id"]] = row
    return disputed


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

    filter_status = st.sidebar.selectbox(
        "Filter",
        ["needs-review", "deepseek-disputed", "pending", "ambiguous", "approved", "corrected", "rejected", "all"],
    )
    disputed = load_verification()
    if filter_status == "needs-review":
        # the true human gate: teacher-flagged records not yet decided
        pool = [e for e in entries if e.get("needs_human_review") and not e.get("review_status")]
    elif filter_status == "deepseek-disputed":
        # decided records leave the disputed queue (find them under approved/corrected/rejected)
        pool = [e for e in entries if e["record_id"] in disputed and not e.get("review_status")]
    else:
        pool = [e for e in entries if filter_status == "all" or (e.get("review_status") or "pending") == filter_status]
    pool.sort(key=queue_sort_key)

    if not pool:
        st.success("Queue empty for this filter.")
        return
    if "record_idx" not in st.session_state:
        st.session_state.record_idx = 1
    index = st.sidebar.number_input("Record", min_value=1, max_value=len(pool), key="record_idx")
    entry = pool[index - 1]
    record = records.get(entry["record_id"], {})
    parsed = entry.get("parsed_annotation") or {}
    dispute = disputed.get(entry["record_id"])

    # a pasted decision belongs to one record: drop it when the shown record changes
    if st.session_state.get("fetched_rid") != entry["record_id"]:
        st.session_state.pop("fetched", None)

    st.title(f"Review: {task} ({index}/{len(pool)} in filter)")
    st.subheader(record.get("title", entry["record_id"]))
    st.caption(f"{record.get('source_id', '?')} · {record.get('canonical_url', '')}")

    # ---- fetch handler: parse the pasted decision JSON ----
    def do_fetch() -> None:
        try:
            pasted = json.loads(st.session_state.get("paste_box", "") or "{}")
        except json.JSONDecodeError as exc:
            st.session_state["fetch_error"] = f"invalid JSON: {exc}"
            return
        if not isinstance(pasted, dict) or not pasted:
            st.session_state["fetch_error"] = "paste a non-empty JSON object"
            return
        # pasted "title" is the reviewer's own tracking aid — ignored here
        st.session_state.pop("fetch_error", None)
        st.session_state["fetched"] = pasted
        st.session_state["fetched_rid"] = entry["record_id"]

    # ---- PANE 2: everything in one copyable box + copy-all underneath ----
    words = (record.get("clean_text") or "").split()
    left_text = "\n".join([
        f'TITLE: {record.get("title", entry["record_id"])}',
        f'SOURCE: {record.get("source_id", "?")} · {record.get("canonical_url", "")}',
        "",
        "SOURCE OPPORTUNITY:",
        " ".join(words[:900]) + (" …" if len(words) > 900 else ""),
        "",
        f'TEACHER TARGET: primary={parsed.get("primary_category")} · '
        f'secondary={parsed.get("secondary_plausible_categories")} · '
        f'ambiguity={parsed.get("classification_ambiguity")}',
        f'REASON: {parsed.get("reason_for_label")}',
        f'FLAGS: {entry.get("review_flags") or []} · validation={entry.get("validation_status")}',
        f'PROVIDER: {entry.get("teacher_provider_slot")} · {entry.get("teacher_model")} · {entry.get("teacher_timestamp")}',
    ])

    fetched = st.session_state.get("fetched") or {}
    fetch_error = st.session_state.get("fetch_error")

    info_pane, fields_pane = st.columns(2)
    with info_pane:
        st.code(left_text, language=None)
        if st.button("Copy all"):
            try:
                import pyperclip

                pyperclip.copy(left_text)
                st.toast("Copied to clipboard")
            except Exception as exc:  # noqa: BLE001 - clipboard can be unavailable
                st.warning(f"clipboard unavailable ({exc}); use the copy icon on the box above")

    with fields_pane:
        if task == "classify":
            categories = load_taxonomy()
            # fetched verdict takes precedence; teacher parsed is the fallback
            base = {**parsed, **{k: v for k, v in fetched.items() if k != "action" and v is not None}}
            current = base.get("primary_category", categories[0])
            primary = st.selectbox(
                "primary_category",
                categories,
                index=categories.index(current) if current in categories else 0,
            )
            secondary = st.multiselect(
                "secondary_plausible_categories",
                [c for c in categories if c != primary],
                default=[s for s in (base.get("secondary_plausible_categories") or []) if s in categories and s != primary],
                help="Dispute or clear the teacher's secondary guesses here.",
            )
            ambiguity = st.number_input(
                "classification_ambiguity",
                min_value=0.0, max_value=1.0,
                value=float(base.get("classification_ambiguity") or 0.0),
                step=0.05,
            )
            reason = st.text_area("reason_for_label", base.get("reason_for_label", ""))
        else:
            edited_summary = st.text_area("summary target", parsed.get("summary", ""), height=360)

        st.caption(
            f'FLAGS: {entry.get("review_flags") or []} · validation={entry.get("validation_status")} · '
            f'provider={entry.get("teacher_provider_slot")}/{entry.get("teacher_model")}'
        )
        if entry.get("adjudication_suggestion"):
            st.info(f"adjudicator ({entry.get('adjudication_provider')}) suggests: {entry['adjudication_suggestion']}")
        if dispute:
            st.warning(
                f"DeepSeek ({dispute.get('verifier_model')}) disputed this: "
                f"{dispute.get('original_label')} -> {dispute.get('verifier_label')}"
                f"\n\nIts reason: {dispute.get('verifier_reason')}"
            )

        st.caption("Paste a decision JSON below and hit Fetch — it fills the fields above.")
        paste_box = st.text_area(
            "paste decision JSON", key="paste_box", height=130,
            placeholder='{"primary_category": "...", "action": "corrected", ...}',
        )
        if st.button("Fetch pasted decision", on_click=do_fetch):
            pass
        if fetch_error:
            st.error(fetch_error)
        elif fetched:
            st.success(f'fetched decision: {fetched.get("title", entry["record_id"])[:60]}')
        # no key here: a keyed widget ignores its value param on later renders,
        # which was why the fetched review_note never showed
        note = st.text_input("review note", value=(fetched or {}).get("review_note", ""))

    _ACTION_MAP = {"approve": "approved", "approved": "approved", "corrected": "corrected",
                   "reject": "reject", "mark ambiguous": "mark ambiguous"}
    default_action = _ACTION_MAP.get((fetched or {}).get("action"), "skip")
    action = st.radio(
        "decision",
        ["skip", "approved", "corrected", "reject", "mark ambiguous"],
        horizontal=True,
        label_visibility="collapsed",
        index=["skip", "approved", "corrected", "reject", "mark ambiguous"].index(default_action),
    )
    if st.button("Save decision") and action != "skip":
        entry["original_teacher_parsed"] = entry.get("original_teacher_parsed") or entry.get("parsed_annotation")
        entry["reviewed_at"] = datetime.now(UTC).isoformat()
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
        # auto-advance: drop the widget state, then set the new initial value —
        # Streamlit forbids mutating a widget key after instantiation
        target = min(index, max(len(pool) - 1, 1))
        st.session_state.pop("record_idx", None)
        st.session_state.record_idx = target
        st.session_state.pop("paste_box", None)   # clear for the next record
        st.session_state.pop("fetched", None)
        st.session_state.pop("fetched_rid", None)
        st.cache_data.clear()
        st.toast(f"Saved: {action} — {record.get('title', '')[:60]}")
        st.rerun()


main()
