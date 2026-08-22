#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

ROOT = Path(__file__).resolve().parents[1]
SITEMAP = ROOT / "sitemap.xml"
MAP = ROOT / "definitive_publication_map.csv"
ART = ROOT / "articulos"
PRESS = ROOT / "prensa"

BASE = "https://nutreconciencia.com"

SECTION_URLS = [
    f"{BASE}/",
    f"{BASE}/articulos/",
    f"{BASE}/prensa/",
    f"{BASE}/libro/",
    f"{BASE}/sobre-mi/",
    f"{BASE}/podcasts/",
]

def clean(v: str) -> str:
    return re.sub(r"\s+", " ", v or "").strip()

def load_established_articles() -> set[str]:
    if not MAP.exists():
        raise FileNotFoundError("definitive_publication_map.csv not found")

    with MAP.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    slugs = {
        clean(r.get("slug", ""))
        for r in rows
        if clean(r.get("is_canonical", "")).lower() == "true"
    }

    slugs.discard("")

    if len(slugs) != 51:
        raise RuntimeError(
            f"Expected 51 established canonical article slugs; found {len(slugs)}"
        )

    return slugs

def load_new_doi_articles() -> set[str]:
    slugs = set()

    for meta in sorted(ART.glob("*/metadata.json")):
        data = json.loads(meta.read_text(encoding="utf-8"))
        doi = clean(data.get("doi", ""))
        if not doi:
            continue

        slug = meta.parent.name
        page = meta.parent / "index.html"
        if not page.exists():
            raise RuntimeError(f"metadata.json without index.html: {slug}")

        # Validate this is actually a canonical article page.
        html = page.read_text(encoding="utf-8", errors="ignore")
        expected = f'<link rel="canonical" href="{BASE}/articulos/{slug}/">'
        if expected not in html:
            raise RuntimeError(f"Non-canonical DOI article page: {slug}")

        slugs.add(slug)

    return slugs

def load_press_urls() -> set[str]:
    urls = set()

    for page in sorted(PRESS.glob("*/index.html")):
        html = page.read_text(encoding="utf-8", errors="ignore")
        m = re.search(
            r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
            html,
            re.I | re.S,
        )
        if not m:
            raise RuntimeError(f"Press page without canonical: {page}")

        url = clean(m.group(1))
        if not url.startswith(f"{BASE}/prensa/"):
            raise RuntimeError(f"Unexpected press canonical: {url}")

        urls.add(url)

    if len(urls) != 19:
        raise RuntimeError(f"Expected 19 press canonical URLs; found {len(urls)}")

    return urls

def validate_article_folders(slugs: set[str]) -> set[str]:
    urls = set()

    for slug in sorted(slugs):
        page = ART / slug / "index.html"
        if not page.exists():
            raise RuntimeError(f"Article index.html missing: {slug}")

        html = page.read_text(encoding="utf-8", errors="ignore")
        expected = f'<link rel="canonical" href="{BASE}/articulos/{slug}/">'
        if expected not in html:
            raise RuntimeError(f"Article canonical mismatch/missing: {slug}")

        if 'id="nutreconciencia-scholarly-article-schema"' not in html:
            raise RuntimeError(f"ScholarlyArticle schema missing: {slug}")

        if '"https://nutreconciencia.com/#person"' not in html:
            raise RuntimeError(f"#person author link missing: {slug}")

        urls.add(f"{BASE}/articulos/{slug}/")

    return urls

def build_sitemap(urls: set[str]) -> str:
    if len(urls) != len(set(urls)):
        raise RuntimeError("Duplicate sitemap URLs detected")

    for url in urls:
        if not re.fullmatch(r"https://nutreconciencia\.com(?:/[^?#]*)?/?", url):
            raise RuntimeError(f"Invalid URL in sitemap set: {url}")
        if "https://nutreconciencia.com/https://" in url:
            raise RuntimeError(f"Malformed duplicated-domain URL: {url}")

    urlset = Element(
        "urlset",
        {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"},
    )

    for url in sorted(urls):
        node = SubElement(urlset, "url")
        loc = SubElement(node, "loc")
        loc.text = url

    raw = tostring(urlset, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(
        indent="  ", encoding="UTF-8"
    ).decode("utf-8")

    # Remove the blank line minidom adds after the XML declaration.
    return pretty.replace('<?xml version="1.0" encoding="UTF-8"?>\n\n',
                          '<?xml version="1.0" encoding="UTF-8"?>\n')

def main() -> None:
    established = load_established_articles()
    new_doi = load_new_doi_articles()
    press = load_press_urls()
    articles = validate_article_folders(established | new_doi)

    urls = set(SECTION_URLS) | press | articles

    # Explicitly assert the expected current architecture.
    if len(established) != 51:
        raise RuntimeError("Established article count changed unexpectedly")
    if len(new_doi) < 1:
        raise RuntimeError("Expected at least one DOI-created article")
    if len(articles) != len(established | new_doi):
        raise RuntimeError("Article URL count mismatch")

    sitemap = build_sitemap(urls)
    SITEMAP.write_text(sitemap, encoding="utf-8")

    # Re-parse the generated file as a final safety check.
    locs = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    if len(locs) != len(urls):
        raise RuntimeError("Generated sitemap LOC count mismatch")
    if len(locs) != len(set(locs)):
        raise RuntimeError("Generated sitemap contains duplicate LOC entries")

    expected_new = (
        f"{BASE}/articulos/"
        "when-ultra-processing-obscures-sustainable-dietary-transitions/"
    )
    if expected_new not in urls:
        raise RuntimeError("Expected new DOI article missing from sitemap")

    print("=" * 72)
    print("STEP 9A FINAL — REBUILD VALID XML SITEMAP")
    print("=" * 72)
    print(f"Section URLs: {len(SECTION_URLS)}")
    print(f"Press URLs: {len(press)}")
    print(f"Established article URLs: {len(established)}")
    print(f"New DOI article URLs: {len(new_doi)}")
    print(f"Total sitemap URLs: {len(urls)}")
    print("XML structure: PASS")
    print("Duplicate URL check: PASS")
    print("Malformed duplicated-domain URL check: PASS")
    print("New DOI article present: PASS")
    print("sitemap.xml: REBUILT")

if __name__ == "__main__":
    main()
