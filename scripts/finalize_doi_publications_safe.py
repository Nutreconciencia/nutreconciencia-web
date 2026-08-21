#!/usr/bin/env python3
"""
STEP 9A FIX — Restore and finalize publication sitemap safely.

Source of truth:
- definitive_publication_map.csv for the 51 established canonical articles.
- every articulos/*/metadata.json for newly automated DOI publications.

Preserves all non-article sitemap entries.
Does NOT delete article pages.
Fails if the definitive map is missing or does not contain 51 canonical rows.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
MAP = ROOT / "definitive_publication_map.csv"
SITEMAP = ROOT / "sitemap.xml"
BASE = "https://nutreconciencia.com/"

def clean(v: str) -> str:
    return re.sub(r"\s+", " ", v or "").strip()

def main():
    if not MAP.exists():
        raise FileNotFoundError("definitive_publication_map.csv not found")
    if not SITEMAP.exists():
        raise FileNotFoundError("sitemap.xml not found")

    with MAP.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    canonical_rows = [
        r for r in rows
        if clean(r.get("is_canonical", "")).lower() == "true"
    ]

    canonical_slugs = set()
    for row in canonical_rows:
        slug = clean(row.get("slug", ""))
        if slug:
            canonical_slugs.add(slug)

    if len(canonical_slugs) != 51:
        raise RuntimeError(
            f"Expected 51 established canonical article slugs; found {len(canonical_slugs)}"
        )

    # Add any newer DOI-created article that has metadata.json.
    new_slugs = set()
    doi_map = {}

    for meta_path in sorted(ART.glob("*/metadata.json")):
        slug = meta_path.parent.name
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        doi = clean(data.get("doi", "")).lower()
        if doi:
            if doi in doi_map:
                raise RuntimeError(
                    f"Duplicate DOI detected: {doi} -> {doi_map[doi]} and {slug}"
                )
            doi_map[doi] = slug
        new_slugs.add(slug)

    all_slugs = canonical_slugs | new_slugs

    # Validate every selected slug has an index.html.
    missing = [
        slug for slug in sorted(all_slugs)
        if not (ART / slug / "index.html").exists()
    ]
    if missing:
        raise RuntimeError(
            "Canonical article directories missing index.html: "
            + ", ".join(missing)
        )

    sitemap = SITEMAP.read_text(encoding="utf-8", errors="ignore")

    # Remove ONLY article URL entries. Preserve everything else verbatim.
    pattern = re.compile(
        r'\s*<url>\s*<loc>https://nutreconciencia\.com/articulos/[^<]+</loc>\s*</url>',
        re.I,
    )
    remaining = pattern.sub("", sitemap)

    close = re.search(r"</urlset>\s*$", remaining, re.I)
    if not close:
        raise RuntimeError("sitemap.xml does not end with </urlset>")

    article_entries = "\n".join(
        f"  <url><loc>{escape(BASE)}articulos/{slug}/</loc></url>"
        for slug in sorted(all_slugs)
    )

    updated = (
        remaining[:close.start()]
        + "\n"
        + article_entries
        + "\n"
        + remaining[close.start():]
    )

    SITEMAP.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("STEP 9A FIX — SAFE PUBLICATION SITEMAP")
    print("=" * 72)
    print(f"Established canonical article URLs: {len(canonical_slugs)}")
    print(f"New DOI metadata slugs: {len(new_slugs)}")
    print(f"Total canonical article URLs in sitemap: {len(all_slugs)}")
    print("Duplicate DOI check: PASS")
    print("Article index.html validation: PASS")
    print("sitemap.xml: RESTORED/UPDATED")
    print("articulos/index.html: NOT MODIFIED")

if __name__ == "__main__":
    main()
