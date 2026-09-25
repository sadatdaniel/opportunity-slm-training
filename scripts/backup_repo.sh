#!/usr/bin/env bash
# Local backup beyond Git (user requirement: GitHub must not be the only backup).
# Creates a timestamped archive of the full working repo EXCLUDING secrets and
# heavy artifacts, keeps the last N=8, and reports. Run from anywhere:
#   bash scripts/backup_repo.sh
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${OI_BACKUP_DIR:-$REPO_DIR/../oi_backups}"
KEEP=8
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
OUT="$BACKUP_DIR/oi_repo_$STAMP.tar.gz"

# Secrets are NEVER archived (.env must be recreated from .env.example).
# Heavy/ignorable dirs (venv, caches, model weights, raw data) are excluded —
# raw data lives in data/raw etc. and is backed up separately if ever needed.
tar -czf "$OUT" -C "$REPO_DIR" \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='.idea' \
    --exclude='__pycache__' \
    --exclude='.env' \
    --exclude='.ruff_cache' \
    --exclude='.pytest_cache' \
    --exclude='models' \
    --exclude='runs' \
    --exclude='data/cache' \
    --exclude='data/raw' \
    --exclude='data/normalized' \
    --exclude='data/curated' \
    --exclude='opportunity_intelligence_weekend_build*.md' \
    .

# corpus jsonl compresses ~10x; this archive now contains the full
# collected corpus with sources - the learnable asset
 echo "backup: $OUT ($(du -h "$OUT" | cut -f1))"

# retention: keep newest KEEP archives
ls -1t "$BACKUP_DIR"/oi_repo_*.tar.gz | tail -n +$((KEEP + 1)) | xargs -r rm --
echo "kept: $(ls -1 "$BACKUP_DIR"/oi_repo_*.tar.gz | wc -l) archive(s) in $BACKUP_DIR"

# integrity check
tar -tzf "$OUT" > /dev/null && echo "integrity: OK"
