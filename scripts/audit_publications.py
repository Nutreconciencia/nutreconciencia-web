#!/usr/bin/env python3
"""
Read-only SEO audit for the research hub.
"""
from __future__ import annotations
import html
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
SITEMAP = ROOT / "sitemap.xml"


def clean(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def norm_title(value: str) -> str:
    value = clean(value).lower()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def extract(pattern: str, text: str, flags=re.I | re.S) -> str:
    m = re.search(pattern, text, flags)
    return clean(m.group(1)) if m else ""


def sitemap_article_slugs() -> set[str]:
    if not SITEMAP.exists():
        return set()
    text = SITEMAP.read_text(encoding="utf-8", errors="ignore")
    slugs = set()
    for m in re.finditer(
        r"<loc>\s*https?://nutreconciencia\.com/articulos/([^<\s/]+?)/?\s*</loc>",
        text, flags=re.I,
    ):
        slugs.add(html.unescape(m.group(1)).strip("/"))
    return slugs


def read_article(folder: Path) -> dict:
    page = folder / "index.html"
    if not page.exists():
        return {}

    text = page.read_text(encoding="utf-8", errors="ignore")

    title = extract(r"<h1[^>]*>(.*?)</h1>", text)
    if not title:
        title = extract(r"<title[^>]*>(.*?)</title>", text)

    canonical = extract(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        text,
    )

    doi = extract(r"""https?://doi\.org/([^"'<\s]+)""", text).rstrip(").,;")
    pmid = extract(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", text)

    noindex = bool(
        re.search(
            r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex',
            text, flags=re.I,
        )
    )

    meta = {}
    meta_file = folder / "orcid.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    doi = doi or clean(str(meta.get("doi") or ""))
    pmid = pmid or clean(str(meta.get("pmid") or ""))
    orcid_work_id = clean(str(
        meta.get("orcid_work_id")
        or meta.get("put_code")
        or meta.get("orcid_put_code")
        or ""
    ))

    return {
        "slug": folder.name,
        "title": title,
        "title_key": norm_title(title),
        "canonical": canonical,
        "doi": doi.lower(),
        "pmid": pmid,
        "orcid_work_id": orcid_work_id,
        "noindex": noindex,
    }


def duplicate_groups(articles, key_name):
    groups = defaultdict(list)
    for a in articles:
        key = a[key_name]
        if key:
            groups[key].append(a["slug"])
    return {k: v for k, v in groups.items() if len(v) > 1}


def main() -> None:
    print("=" * 72)
    print("NUTRECONCIENCIA — SEO / PUBLICATION INVENTORY AUDIT")
    print("=" * 72)

    sitemap_slugs = sitemap_article_slugs()
    print(f"\nSitemap article URLs: {len(sitemap_slugs)}")

    articles = []
    if ART.exists():
        for folder in sorted(ART.iterdir()):
            if folder.is_dir():
                meta = read_article(folder)
                if meta:
                    articles.append(meta)

    indexable = [a for a in articles if not a["noindex"]]
    noindex = [a for a in articles if a["noindex"]]

    in_sitemap = [a for a in indexable if a["slug"] in sitemap_slugs]
    missing_from_sitemap = [a for a in indexable if a["slug"] not in sitemap_slugs]
    sitemap_orphans = sorted(sitemap_slugs - {a["slug"] for a in indexable})

    dup_title = duplicate_groups(indexable, "title_key")
    dup_doi = duplicate_groups(indexable, "doi")
    dup_pmid = duplicate_groups(indexable, "pmid")
    dup_orcid = duplicate_groups(indexable, "orcid_work_id")

    bad_canonical = []
    for a in indexable:
        expected = f"https://nutreconciencia.com/articulos/{a['slug']}/"
        if a["canonical"] and a["canonical"].rstrip("/") != expected.rstrip("/"):
            bad_canonical.append((a["slug"], a["canonical"], expected))

    print(f"Article folders with index.html: {len(articles)}")
    print(f"Indexable article folders: {len(indexable)}")
    print(f"noindex article folders: {len(noindex)}")
    print(f"Indexable articles present in sitemap: {len(in_sitemap)}")
    print(f"Indexable articles missing from sitemap: {len(missing_from_sitemap)}")
    print(f"Sitemap URLs without matching indexable folder: {len(sitemap_orphans)}")
    print(f"Duplicate title groups: {len(dup_title)}")
    print(f"Duplicate DOI groups: {len(dup_doi)}")
    print(f"Duplicate PMID groups: {len(dup_pmid)}")
    print(f"Duplicate ORCID work groups: {len(dup_orcid)}")
    print(f"Canonical mismatches: {len(bad_canonical)}")

    if missing_from_sitemap:
        print("\n--- MISSING FROM SITEMAP ---")
        for a in missing_from_sitemap:
            print(f"{a['slug']} | {a['title']}")

    if sitemap_orphans:
        print("\n--- SITEMAP ORPHANS ---")
        for slug in sitemap_orphans:
            print(slug)

    if dup_title:
        print("\n--- DUPLICATE TITLES ---")
        for _, slugs in sorted(dup_title.items()):
            print(" | ".join(slugs))

    if dup_doi:
        print("\n--- DUPLICATE DOI ---")
        for key, slugs in sorted(dup_doi.items()):
            print(f"{key} -> {' | '.join(slugs)}")

    if dup_pmid:
        print("\n--- DUPLICATE PMID ---")
        for key, slugs in sorted(dup_pmid.items()):
            print(f"{key} -> {' | '.join(slugs)}")

    if dup_orcid:
        print("\n--- DUPLICATE ORCID WORK ---")
        for key, slugs in sorted(dup_orcid.items()):
            print(f"{key} -> {' | '.join(slugs)}")

    if bad_canonical:
        print("\n--- CANONICAL MISMATCHES ---")
        for slug, found, expected in bad_canonical:
            print(f"{slug} | found={found} | expected={expected}")

    print("\n--- QUICK INVENTORY ---")
    print(f"Total article folders: {len(articles)}")
    print(f"Indexable: {len(indexable)}")
    print(f"In sitemap: {len(in_sitemap)}")
    print(f"Missing sitemap: {len(missing_from_sitemap)}")
    print(f"Sitemap orphans: {len(sitemap_orphans)}")
    print(f"Duplicate title groups: {len(dup_title)}")
    print(f"Duplicate DOI groups: {len(dup_doi)}")
    print(f"Duplicate PMID groups: {len(dup_pmid)}")
    print(f"Duplicate ORCID work groups: {len(dup_orcid)}")
    print(f"Canonical mismatches: {len(bad_canonical)}")
    print("\nAUDIT ONLY — no files were modified.")


if __name__ == "__main__":
    main()
