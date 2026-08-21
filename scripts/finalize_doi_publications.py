#!/usr/bin/env python3
"""
STEP 9A — Finalize DOI-created publications safely.

This is the second phase of the DOI automation.

It:
1. scans all articulos/*/metadata.json files;
2. detects duplicate DOIs;
3. rebuilds the article portion of sitemap.xml from all canonical article
   folders;
4. verifies every article page has canonical + ScholarlyArticle + #person;
5. does NOT modify articulos/index.html yet (that requires matching the
   current editorial layout rather than guessing selectors).

Exit 1 if duplicate DOIs or malformed article pages are found.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
SITEMAP = ROOT / "sitemap.xml"

BASE = "https://nutreconciencia.com/"

def clean(v: str) -> str:
    return re.sub(r"\s+", " ", v or "").strip()

def main() -> None:
    metadata_files = sorted(ART.glob("*/metadata.json"))
    article_slugs = []
    doi_map: dict[str, list[str]] = {}
    errors = []

    for meta_path in metadata_files:
        slug = meta_path.parent.name
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{slug}: invalid metadata.json ({exc})")
            continue

        doi = clean(data.get("doi", "")).lower()
        page = meta_path.parent / "index.html"

        if not page.exists():
            errors.append(f"{slug}: metadata exists but index.html is missing")
            continue

        if doi:
            doi_map.setdefault(doi, []).append(slug)

        text = page.read_text(encoding="utf-8", errors="ignore")

        if f'<link rel="canonical" href="{BASE}articulos/{slug}/">' not in text:
            errors.append(f"{slug}: canonical missing or not canonical")
        if 'id="nutreconciencia-scholarly-article-schema"' not in text:
            errors.append(f"{slug}: ScholarlyArticle schema missing")
        if '"https://nutreconciencia.com/#person"' not in text:
            errors.append(f"{slug}: #person author link missing")

        article_slugs.append(slug)

    duplicates = {doi: slugs for doi, slugs in doi_map.items() if len(slugs) > 1}

    if duplicates:
        print("DUPLICATE DOI(S) FOUND:")
        for doi, slugs in sorted(duplicates.items()):
            print(f" - {doi}: {', '.join(slugs)}")
        raise SystemExit(1)

    if errors:
        print("ARTICLE VALIDATION ERRORS:")
        for error in errors:
            print(" -", error)
        raise SystemExit(1)

    if not SITEMAP.exists():
        raise FileNotFoundError("sitemap.xml not found")

    sitemap = SITEMAP.read_text(encoding="utf-8", errors="ignore")

    # Remove only the article URL entries from the sitemap; preserve every
    # other section/page entry exactly as it is.
    pattern = re.compile(
        r'\s*<url>\s*<loc>https://nutreconciencia\.com/articulos/[^<]+</loc>\s*</url>',
        re.I,
    )
    sitemap_without_articles = pattern.sub("", sitemap)

    entries = "\n".join(
        f"  <url><loc>{escape(BASE)}articulos/{slug}/</loc></url>"
        for slug in sorted(set(article_slugs))
    )

    close = re.search(r"</urlset>\s*$", sitemap_without_articles, re.I)
    if not close:
        raise RuntimeError("sitemap.xml does not end with </urlset>")

    new_sitemap = (
        sitemap_without_articles[:close.start()]
        + "\n"
        + entries
        + "\n"
        + sitemap_without_articles[close.start():]
    )
    SITEMAP.write_text(new_sitemap, encoding="utf-8")

    print("=" * 72)
    print("STEP 9A — DOI PUBLICATION FINALIZATION")
    print("=" * 72)
    print(f"Metadata files scanned: {len(metadata_files)}")
    print(f"Unique DOI values: {len(doi_map)}")
    print(f"Canonical article URLs in sitemap: {len(set(article_slugs))}")
    print("Duplicate DOI check: PASS")
    print("Article schema validation: PASS")
    print("sitemap.xml: UPDATED")
    print("articulos/index.html: NOT MODIFIED")


if __name__ == "__main__":
    main()
