#!/usr/bin/env python3
"""
STEP 5B — Add ScholarlyArticle JSON-LD to canonical research pages.

READ/MODIFY:
- modifies only canonical article index.html files listed by
  definitive_publication_map.csv
- does not modify legacy pages
- does not modify sitemap.xml or .htaccess

Schema links every article to:
https://nutreconciencia.com/#person

The script extracts title, DOI, PMID, date, and journal from the canonical page
where available. Missing fields are omitted rather than guessed.
"""

from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "definitive_publication_map.csv"
ART = ROOT / "articulos"


def clean(v: str) -> str:
    v = html.unescape(v or "")
    return re.sub(r"\s+", " ", v).strip()


def extract(pattern: str, text: str) -> str:
    m = re.search(pattern, text, flags=re.I | re.S)
    return clean(m.group(1)) if m else ""


def first_nonempty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def build_schema(slug: str, text: str, row: dict) -> dict:
    title = extract(r"<h1[^>]*>(.*?)</h1>", text)
    if not title:
        title = extract(r"<title[^>]*>(.*?)</title>", text)
    if not title:
        title = clean(row.get("title", ""))

    doi = first_nonempty(
        clean(row.get("doi", "")),
        extract(r"""https?://doi\.org/([^"'<\s]+)""", text).rstrip(").,;"),
    )

    pmid = first_nonempty(
        clean(row.get("pmid", "")),
        extract(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", text),
    )

    canonical = extract(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        text,
    )
    canonical = first_nonempty(
        canonical,
        f"https://nutreconciencia.com/articulos/{slug}/",
    )

    # Common date patterns used by generated article pages.
    date_published = first_nonempty(
        extract(r'"datePublished"\s*:\s*"([^"]+)"', text),
        extract(r'(?:Publicado|Publication date|Published)\s*[:\-]</?[^>]*>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', text),
        extract(r'\b(20[0-9]{2}-[0-9]{2}-[0-9]{2})\b', text),
    )

    journal = first_nonempty(
        extract(r'(?:<span[^>]*class=["\'][^"\']*(?:journal|revista)[^"\']*["\'][^>]*>|(?:Journal|Revista)\s*[:\-])\s*([^<\n]+)', text),
        extract(r'"publisher"\s*:\s*\{[^}]*?"name"\s*:\s*"([^"]+)"', text),
    )

    same_as = []
    if doi:
        same_as.append(f"https://doi.org/{doi}")
    if pmid:
        same_as.append(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")

    schema = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "@id": canonical.rstrip("/") + "/#article",
        "url": canonical,
        "headline": title,
        "author": {
            "@type": "Person",
            "@id": "https://nutreconciencia.com/#person",
        },
    }

    if date_published:
        # Normalize simple ISO dates/years only; omit ambiguous values.
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date_published) or re.fullmatch(r"20\d{2}", date_published):
            schema["datePublished"] = date_published

    if journal:
        schema["isPartOf"] = {
            "@type": "Periodical",
            "name": journal,
        }

    if same_as:
        schema["sameAs"] = same_as

    return schema


def inject_schema(text: str, schema: dict) -> str:
    # Remove an earlier copy created by this workflow.
    text = re.sub(
        r'\s*<script type="application/ld\+json" id="nutreconciencia-scholarly-article-schema">.*?</script>\s*',
        "\n",
        text,
        flags=re.I | re.S,
    )

    block = (
        '<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">\n'
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + "\n</script>\n"
    )

    marker = re.search(r"</head>", text, flags=re.I)
    if not marker:
        raise RuntimeError("No </head> found")

    return text[:marker.start()] + block + text[marker.start():]


def main():
    if not MAP.exists():
        raise FileNotFoundError("definitive_publication_map.csv not found")

    with MAP.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    canonical_rows = [r for r in rows if (r.get("is_canonical") or "").strip().lower() == "true"]

    if len(canonical_rows) != 51:
        raise RuntimeError(f"Expected 51 canonical article rows, found {len(canonical_rows)}")

    modified = 0
    missing = []

    for row in canonical_rows:
        slug = clean(row.get("slug", ""))
        path = ART / slug / "index.html"
        if not path.exists():
            missing.append(slug)
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        schema = build_schema(slug, text, row)
        updated = inject_schema(text, schema)

        if updated != text:
            path.write_text(updated, encoding="utf-8")
            modified += 1

    if missing:
        raise RuntimeError("Missing canonical article pages: " + ", ".join(missing))

    print("=" * 72)
    print("STEP 5B — SCHOLARLY ARTICLE SCHEMA")
    print("=" * 72)
    print(f"Canonical article pages processed: {len(canonical_rows)}")
    print(f"Pages modified: {modified}")
    print("Author entity: https://nutreconciencia.com/#person")
    print("Legacy article pages were not modified.")
    print("sitemap.xml and .htaccess were not modified.")

if __name__ == "__main__":
    main()
