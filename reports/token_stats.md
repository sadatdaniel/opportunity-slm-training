# Token Statistics (real Supra tokenizer)

Model: `SupraLabs/Supra2-100M-Instruct` · corpus records: 3296 · measured locally

| measurement | p50 | p90 | p95 | p99 | max | ≤512 | ≤768 | ≤1024 | ≤1536 | ≤2048 |
|---|---|---|---|---|---|---|---|---|---|---|
| input only (600-word truncated) | 714 | 890 | 924 | 1016 | 1784 | 27% | 57% | 99% | 100% | 100% |
| input + proxy target (~150w) | 765 | 941 | 975 | 1067 | 1835 | 20% | 50% | 98% | 100% | 100% |
| full clean_text, no truncation | 758 | 4050 | 4949 | 6405 | 28944 | 23% | 51% | 64% | 75% | 80% |

## Reading

- 98% of prompt+target sequences fit the 1,024-token context the base model was primarily trained around.
- 100% fit within 2,048 tokens.
- Input is truncated at 600 words before measurement; critical eligibility text is front-loaded by the cleaning pipeline. Long-tail records (see full_text) rely on truncation and must be handled explicitly at training time, never silently.
