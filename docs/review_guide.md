# Human Review Guide — what to check and what to write

The one universal question first:

> **Is this an opportunity posting at all?**
> Research news, press releases about study results, "X person won Y" stories,
> obituaries, rankings, conference reports → **reject** (no summary needed,
> nothing for the model to learn). If yes → decide the task below.

---

## Task: classify — "what is being OFFERED to the applicant?"

Pick the ONE category that names the **primary offer**, then optionally 0-2
plausible secondaries.

| category | pick it when the posting's core offer is... |
|---|---|
| scholarships | money/stipend **to fund study** (any level — masters/PhD funding is still a scholarship unless it's a job) |
| fellowships | a selective structured **program** (research stay, leadership, cohort) — usually named "fellowship" |
| phd | a **doctoral position or admission** ("join our PhD programme", employed PhD) |
| postdoc | a **postdoctoral position/fellowship** (career-stage job) |
| grants | money for a **project, research, or organization** — not personal study |
| internships | a **work-experience placement** (traineeships count) |
| competitions | a **contest** where participants compete and win |
| awards | **recognition for past work** (prizes, honorary things) |
| conferences | **attending/speaking at an event** |
| workshops | **being trained** (short courses, summer schools, webinars) |
| exchange_programs | **mobility between institutions/countries** as the core offer |
| miscellaneous | announcements, digests, everything without a clear applicant offer |

### Boundary rules (the recurring hard cases)

- "PhD **scholarship**" (money to do a PhD): if the offer is *the position/
  admission* → **phd**; if it's purely *the money for study costs* →
  **scholarships**. When genuinely torn → primary phd, secondary
  scholarships, ambiguity 0.4-0.6.
- "**X awarded Y**" news → not awards; usually **miscellaneous** or reject.
- "Compiled list of opportunities" digests → **miscellaneous** (the post
  itself is not one opportunity).
- Workshops inside a conference, travel grants inside a fellowship → the
  **primary offer** wins; the rest may be a secondary.
- Event date ≠ application deadline (doesn't affect category, but watch it
  in summarize).

### What to write

- **secondary_plausible_categories**: only genuinely defensible
  alternatives (0-2). Empty is a valid answer.
- **classification_ambiguity**: how torn *you* are. 0.0-0.2 obvious,
  0.3-0.5 lean-with-doubt, 0.6+ could genuinely be two.
- **reason_for_label**: one sentence naming the *deciding fact* ("a 3-day
  capacity-building training with defined modules" beats "it is a workshop").
- **reject** when: news article, press release, no applicant offer at all.

---

## Task: summarize — write the sectioned plain-text summary

Paste format: `{"summary": "...", "review_note": "...", "action": "..."}`

Only extract what is **explicitly stated**. Never invent a deadline, amount,
or condition. Never silently infer a year.

### Section order (omit empty sections)

```
DEADLINE
MANDATORY
RESTRICTIONS
TARGET GROUP
FUNDING / BENEFITS
APPLICATION
OTHER IMPORTANT CONDITIONS
SUMMARY
```

### What goes where — and the traps

- **DEADLINE**: *application* deadline only. Event dates, nomination
  deadlines, interview dates are NOT application deadlines — label each
  separately if several matter. Add status: explicit / rolling / not_stated.
- **MANDATORY**: only hard requirements ("must", "required", "only open to").
  Preserve logic exactly: "German OR French" stays OR; "or equivalent
  experience" stays; "under 40" stays "under 40" (not "40 or younger").
- **RESTRICTIONS**: exclusions and negative conditions ("must not have
  previously received X", country exclusions).
- **TARGET GROUP**: who it's for (students, Africans, women in STEM,
  early-career...).
- **FUNDING / BENEFITS**: exact amounts and what's covered; "full fees" is
  exact. What's NOT covered (self-funded travel) belongs here too.
- **APPLICATION**: how/where to apply, required documents, nomination rules.
- **OTHER IMPORTANT CONDITIONS**: mandatory attendance, prior-funding
  exclusions, GPA thresholds — anything limiting not covered above.
- **SUMMARY**: 2-4 sentence natural-language recap. The sections carry the
  facts; the SUMMARY never becomes the only place a fact exists.
- "Preferred" qualifications go to PREFERRED/OTHER — never upgrade them into
  MANDATORY. "Normally expected" is not an absolute rule.

### Hard limits

- ≤150 words total (a little over is accepted, but aim hard at 150).
- Conditions terse; accuracy beats prose.
- Not an opportunity → **reject** (no summary needed).

---

## Actions, briefly

- **approved**: teacher output is correct as-is.
- **corrected**: you changed anything (category, secondary, ambiguity,
  reason, summary). Auto-selected when you edit and press approve.
- **reject**: not an opportunity / garbage extraction.
- **mark ambiguous**: genuinely undecidable — leave it for a later pass.
