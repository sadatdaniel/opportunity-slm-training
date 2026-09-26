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
uv sync

# Corpus pipeline
uv run python -m project.sources.registry            # rebuild sources/registry.yaml
uv run python -m project.sources.inventory           # probe sources (APIs, feeds, robots)
uv run python -m project.collect --source SOURCE_ID  # collect raw records
uv run python -m project.collect --all --methods wp_rest,rss
uv run python -m project.normalize                   # raw -> normalized English records
uv run python -m project.dedupe                      # layered dedup + duplicate groups
uv run python -m project.freeze_corpus               # freeze corpus_v1 (immutable manifest)

# Measurement & audits
uv run python -m project.token_stats                 # real Supra tokenizer statistics
uv run python -m project.audit                       # taxonomy audit sample + imbalance

# Teacher annotation (multi-provider pool; needs API keys in .env)
uv run python -m project.annotate --task classify --pilot    # ~200 stratified pilot
uv run python -m project.annotate --task classify            # full corpus
uv run python -m project.annotate --task summarize --pilot 300

# Datasets
uv run python -m project.build_dataset --task classify      # after annotation
uv run python -m project.build_dataset --task summarize

# Tests
uv run pytest
```

## Status

See `PROJECT_STATUS.md` (live state) and `AGENT_PICKUP.md` (agent entry point:
snapshot, work queue, machine setup, do/don't rules). Current highlights:

- corpus: 4,670 canonical records from 19 sources (target ~10k), fully
  annotated for both capabilities and independently verified
- classifier v0.2.0 released: 84.3% accuracy / macro F1 0.733 (see Releases)
- summarizer v0.3.0 trained with stable-prompt boundary fix; evaluation in flight

## Data pipeline (continuous batch loop)

```bash
uv run python -m project.collect --all --methods wp_rest,rss   # 1. collect
uv run python -m project.normalize && uv run python -m project.dedupe   # 2. clean
uv run python -m project.annotate --task classify --workers 8  # 3. label (multi-provider)
uv run python -m project.verify_bulk --task classify --provider experiential --resume --skip-consensus  # 4. verify
uv run python -m project.consensus --task classify --emit-verify-list   # 5. merge verdicts
uv run python -m project.build_dataset --task classify --version vN+1 --consensus data/annotations/consensus_classify.jsonl  # 6. freeze
```

Only consensus-clean data trains. Every step is resumable.
