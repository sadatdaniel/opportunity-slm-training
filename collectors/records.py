"""Normalized record construction with full provenance (build brief section 12).

Every collected record keeps raw and cleaned text separately, a stable record
id derived from the canonical URL, a content hash for deduplication, and
retrieval metadata. Extra source-specific fields ride along in ``extra``.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from html import unescape

from bs4 import BeautifulSoup

# Deterministic namespace so the same canonical URL always yields the same id.
RECORD_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "opportunity-intelligence/records/v1")

PARSER_VERSION = 1

RAW_TEXT_LIMIT = 400_000  # safety valve for pathological pages


def html_to_text(html: str) -> str:
    """Readable text from HTML, preserving headings, lists, and paragraphs.

    Block-level elements become line breaks so sections like "Eligibility",
    "Benefits", "Deadline" survive as structure — the cleaning pipeline (brief
    section 13) depends on these staying intact.
    """
    if not html or "<" not in html:
        return unescape(html or "").strip()
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(
        ["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote", "section", "article"]
    ):
        block.append("\n")
    text = soup.get_text()
    lines = (re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines())
    out: list[str] = []
    blanks = 0
    for line in lines:
        if line:
            out.append(line)
            blanks = 0
        else:
            blanks += 1
            if blanks == 1:
                out.append("")
    return "\n".join(out).strip()[:RAW_TEXT_LIMIT]


def content_hash(text: str) -> str:
    """Hash of whitespace-normalized text, used for exact/near dedup."""
    normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def stable_record_id(canonical_url: str) -> str:
    return str(uuid.uuid5(RECORD_NAMESPACE, canonical_url))


def make_record(
    *,
    source_id: str,
    source_name: str,
    canonical_url: str,
    title: str,
    raw_text: str,
    clean_text: str | None = None,
    source_url: str = "",
    listing_url: str = "",
    published_at: str | None = None,
    deadline: str | None = None,
    extra: dict | None = None,
) -> dict:
    title = unescape(title or "").strip()
    clean_text = clean_text if clean_text is not None else html_to_text(raw_text or "")
    return {
        "record_id": stable_record_id(canonical_url),
        "source_id": source_id,
        "source_name": source_name,
        "source_url": source_url,
        "canonical_url": canonical_url,
        "listing_url": listing_url,
        "title": title,
        "raw_text": (raw_text or "")[:RAW_TEXT_LIMIT],
        "clean_text": clean_text,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "published_at": published_at,
        "deadline": deadline,
        "content_hash": content_hash(f"{title}\n{clean_text}"),
        "parser_version": PARSER_VERSION,
        "language": None,  # detected during normalization
        "extra": extra or {},
    }
