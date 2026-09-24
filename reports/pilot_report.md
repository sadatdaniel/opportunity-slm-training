# Teacher Annotation Pilot Report (v3 brief step 5)

Date: 2026-09-24 · Task: classification · Target: 200 stratified records
Result: **194 unique records annotated, 179 valid (92%), 15 flagged for review (8%)**

## Pipeline behavior

- Routing worked as designed: 160 records on gemini_1, 28 on gemini_2, 6 on
  gemini_3 (rotation as each slot's rolling-minute budget filled). OpenRouter
  and Z.ai were NOT called for easy cases — only for the 15 ambiguous ones.
- After fixing the Z.ai provider (Coding Plan endpoint) and the ambiguity
  threshold (only genuinely torn records earn extra calls), adjudication ran
  on ambiguous cases: 2 agree, 4 disagree, 9 pre-fix unavailable.
- No schema-validation failures on the final run; invalid-output recovery via
  second opinion was implemented but never needed on the pilot.

## Category distribution (teacher labels)

workshops 28 · fellowships 27 · miscellaneous 19 · internships 18 ·
conferences 17 · awards 16 · competitions 14 · grants 14 · postdoc 13 ·
scholarships 12 · phd 11 · exchange_programs 5

All 12 taxonomy_v1 categories are represented; exchange_programs remains thin
(matches the imbalance report's prediction).

## Ambiguity pairs (where the teacher hesitated)

| pair | count |
|---|---|
| workshops <-> conferences | 2 |
| grants <-> scholarships, fellowships | 2 |
| scholarships <-> fellowships, grants | 2 |
| competitions <-> awards | 1 |
| phd <-> exchange_programs, fellowships | 1 |
| phd <-> fellowships, grants | 1 |
| postdoc <-> fellowships, grants | 1 |
| fellowships <-> workshops, grants | 1 |
| fellowships <-> grants, postdoc | 1 |
| competitions <-> workshops, conferences | 1 |
| awards <-> grants, fellowships | 1 |
| exchange_programs <-> fellowships | 1 |

These map almost exactly onto the "known ambiguity pairs" predicted in
`reports/taxonomy_v1.md` before any labeling — the taxonomy analysis was
correct about where definitional overlap lives.

## Teacher error patterns observed

1. Mandatory-vs-preferred is the main risk for downstream Noul questions, not
   for classification. The classify prompt handles it; Noul criteria must
   encode "mandatory" explicitly (brief 4A's German example).
2. News-style posts (press releases, announcements) land in miscellaneous —
   about 10% of the pilot. Fine as a class; no evidence of misclassification
   into real opportunity categories.
3. Boundary confusion concentrates on fellowship/phd/postdoc/grants —
   consistent with the taxonomy audit. The 4 adjudicator disagreements were
   all in this band. These need human review before trusting silver labels.

## Human review requirement before dataset freeze

The 15 flagged records must be human-reviewed (review queue ready:
`uv run streamlit run project/review.py`) before `classifier_dataset_v1`.
The 9 pre-fix "adjudication_unavailable" flags are review-priority too.
An additional spot-check of ~20 unflagged silver labels is recommended to
estimate the true silver error rate before annotating the full corpus.

## Decision

Teacher quality looks acceptable to proceed to full-corpus classification
annotation AFTER human review of the 15 flagged records and the 20-record
spot check (brief step 6 gate). Summarizer pilot (step 9) can start in
parallel — it uses different prompts and does not consume the same gate.
