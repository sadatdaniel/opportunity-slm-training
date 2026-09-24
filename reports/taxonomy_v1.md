# Taxonomy v1

Status: **active** for classifier dataset v1. Changes from here create
`taxonomy_v2` — never mutate this file silently (brief section 7).

## Decision

Twelve canonical categories: the brief's eight baseline categories plus four
that corpus evidence shows are semantically distinct:

| category | baseline or new | evidence (wave-1 corpus, 2,054 records) |
|---|---|---|
| scholarships | baseline | 358 title cues; 134 WP terms |
| fellowships | baseline | 222 title cues; 170+96 WP terms |
| phd | **new** | 136 title cues; distinct population (doctoral positions/admissions, not study funding) |
| postdoc | **new** | 59 title cues; always job/fellowship-shaped, never other types |
| grants | **new** | 93 title cues; 68 WP terms; project/organization funding ≠ study funding |
| internships | baseline | 73 title cues; 73 WP terms |
| competitions | baseline | 36 title cues |
| awards | **new** | 66 title cues; recognition/honors ≠ contests |
| conferences | baseline | 56 title cues (+summits in titles) |
| workshops | baseline | 74 title cues |
| exchange_programs | baseline | rare in titles (4) but present in source scopes |
| miscellaneous | baseline | news-style posts, press releases, everything else |

## Deliberately NOT categories

- `masters`, `undergraduate`: academic LEVELS, not opportunity types — a
  masters scholarship is a scholarship. Aliased to `scholarships`.
- `summer_schools`: short training programs → aliased to `workshops`.
- `research_grants`, `doctoral_grants`, `travel_grants`: aliased to `grants`.

## Signals are not labels

WP site categories are dominated by geography and boilerplate (europe, africa,
closed, articles...) and over half of titles carry no type keyword
(`no_signal: 1074/2054`). This is exactly why the brief forbids using source
scope or site categories as training labels: labels come from the teacher
model + human review, and this taxonomy only bounds the classifier's output
space.

## Known ambiguity pairs (expect teacher/human review volume here)

- fellowship vs scholarship (funded study positions)
- grant vs scholarship (organization funding vs individual study funding)
- competition vs award (contest vs recognition)
- phd vs postdoc (position level)
- workshops vs conferences (multi-track events)
