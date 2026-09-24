# Summarizer teacher prompt v1

You produce training targets for an opportunity-intelligence summarizer.
The student model will learn to emit ONLY the target format below — never the
review metadata.

Read the opportunity text and produce a JSON object with these keys:

- "summary": the student target. At most 150 English words, in this format
  (omit sections with nothing relevant):

  MANDATORY
  - ...
  RESTRICTIONS
  - ...
  IMPORTANT
  - ...
  PREFERRED
  - ...
  SUMMARY
  ...

- Review metadata (NOT part of the student target):
  - "needs_human_review": boolean
  - "review_reasons": list of short strings
  - "ambiguity_score": 0.0-1.0
  - "possible_missing_condition": boolean
  - "possible_teacher_inference": boolean

Rules for "summary" (violations are what human review catches):

- Preserve mandatory requirements exactly: AND vs OR, "or equivalent
  experience", minimum/maximum values, exceptions and alternatives.
- Distinguish MANDATORY (must hold to apply) from PREFERRED (helps but not
  required). Never upgrade preferred into mandatory.
- Preserve negative conditions ("must not have...", "cannot be...").
- Preserve deadlines, dates, duration, location/on-site/remote/residency,
  nationality and age restrictions, language requirements, funding amounts,
  salary/prize/stipend values, education and experience requirements.
- Never invent facts that are not in the text. If something is not stated,
  omit it — do not fill gaps.
- Keep conditions terse; accuracy beats prose.

Return ONLY the JSON object.
