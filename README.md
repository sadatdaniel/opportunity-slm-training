# Opportunity Intelligence

An end-to-end, reproducible platform for training and serving very small
specialist models ("System-One style") that process opportunity postings:
scholarships, fellowships, competitions, internships, conferences, and similar.

The platform starts with two capabilities and is designed so new specialist
capabilities can be added later without restructuring:

| Capability | Endpoint | Model family | Method |
|---|---|---|---|
| Opportunity summarization | `POST /v1/summarize` | Supra2-100M-based summarizer | supervised fine-tuning (autoregressive) |
| Opportunity classification | `POST /v1/categorize` | Supra2-100M-based classifier vs. System-One baselines | one forward pass, classification head |

There is deliberately **no** generic chat/completion endpoint. Each capability
is independently trainable, evaluatable, versioned, and deployable.

## Layout

```
project/          pipeline package (sources, collection, datasets)
collectors/       polite HTTP fetching framework (cache, rate limit, robots)
training/         per-capability training/evaluation code (summarizer, classifier)
recipes/          reusable per-source collection recipes
sources/          source registry (normalized from 100_academic_sources.md)
data/             raw, normalized, curated data + manifests (raw data not in git)
datasets/         versioned, split, frozen datasets per capability
models/           versioned model artifacts (not in git)
reports/          inventory, taxonomy, and analysis reports
experiments/      one report per training run + run manifests
config/           taxonomy and capability configuration
docs/             learning notes and architecture docs
tests/            unit tests, fixture-based parser tests
```

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Commands (current)

```bash
# Rebuild sources/registry.yaml from the human-curated 100_academic_sources.md
uv run python -m project.sources.registry

# Probe every registered source (APIs, feeds, robots) and write the inventory
uv run python -m project.sources.inventory

# Run tests
uv run pytest
```

Planned commands (collection, annotation, training) are tracked in
`PROJECT_STATUS.md` and will appear here as they land.

## Status

See `PROJECT_STATUS.md` for the current phase, completed milestones, and any
human actions required.
