#!/usr/bin/env python3
"""
One-time SEO migration for Nutreconciencia article URLs.

It does NOT depend on orcid.json. It scans every article folder and identifies
legacy duplicates against canonical folders listed in sitemap.xml using DOI,
PMID and/or normalized H1/title. It then writes managed 301 redirects to .htaccess.

It also adds:
- /articulos/index.html -> /articulos/
- /prensa/index.html -> /prensa/
- /libro/index.html -> /libro/
- /sobre-mi/index.html -> /sobre-mi/
- /podcasts/index.html -> /podcasts/

No article HTML is deleted.
"""

from __future__ import annotations

import html as html_lib
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"

BEGIN = "# BEGIN NUTRECONCIENCIA SEO REDIRECTS"
END = "# END NUTRECONCIENCIA SEO REDIRECTS"


def normalize_text(value: str) -> str:
    value = html_lib.unescape(value or "").lower()
    value = value.replace("‐", "-").replace("–", "-").replace("—", "-")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def canonical_slugs() -> set[str]:
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        return set()

    text = sitemap.read_text(encoding="utf-8", errors="ignore")
    slugs = set()
    for match in re.finditer(
        r"https?://nutreconciencia\.com/articulos/([^<\s/]+)(?:/)?",
        text,
        flags=re.I,
    ):
        slugs.add(html_lib.unescape(match.group(1)).strip("/"))
    return slugs


def extract_page_meta(folder: Path) -> dict:
    page = folder / "index.html"
    if not page.exists():
        return {}

    text = page.read_text(encoding="utf-8", errors="ignore")

    canonical = ""
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', text, re.I)
    if m:
        canonical = m.group(1)

    h1 = ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S)
    if m:
        h1 = re.sub(r"<[^>]+>", " ", m.group(1))

    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if m:
        title = re.sub(r"<[^>]+>", " ", m.group(1))

    doi = ""
    m = re.search(r"https?://doi\.org/([^\"'<\s]+)", text, re.I)
    if m:
        doi = urllib.parse.unquote(m.group(1)).rstrip(").,;")

    pmid = ""
    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", text, re.I)
    if m:
        pmid = m.group(1)

    return {
        "folder": folder.name,
        "canonical": canonical,
        "h1": html_lib.unescape(h1).strip(),
        "title": html_lib.unescape(title).strip(),
        "doi": doi.lower().strip(),
        "pmid": pmid.strip(),
    }


def best_key(meta: dict) -> tuple[str, str]:
    # Prefer DOI, then PMID, then normalized visible title.
    if meta["doi"]:
        return ("doi", meta["doi"])
    if meta["pmid"]:
        return ("pmid", meta["pmid"])
    return ("title", normalize_text(meta["h1"] or meta["title"]))


def choose_pair(canonical_meta: dict, legacy_meta: dict) -> bool:
    ck = best_key(canonical_meta)
    lk = best_key(legacy_meta)
    return ck[1] and lk[1] and ck == lk


def main() -> None:
    canon_slugs = canonical_slugs()
    all_meta = []

    for folder in sorted(ART.iterdir()):
        if folder.is_dir():
            meta = extract_page_meta(folder)
            if meta:
                all_meta.append(meta)

    canon = [m for m in all_meta if m["folder"] in canon_slugs]
    legacy = [m for m in all_meta if m["folder"] not in canon_slugs]

    redirects: dict[str, str] = {}
    ambiguous = []

    # Strong matching: DOI and PMID are exact. Title fallback is only used when
    # neither page exposes DOI nor PMID.
    for old in legacy:
        matches = []
        for new in canon:
            if old["doi"] and new["doi"] and old["doi"] == new["doi"]:
                matches.append(new)
            elif old["pmid"] and new["pmid"] and old["pmid"] == new["pmid"]:
                matches.append(new)
            elif not old["doi"] and not old["pmid"] and not new["doi"] and not new["pmid"]:
                if normalize_text(old["h1"] or old["title"]) == normalize_text(new["h1"] or new["title"]):
                    matches.append(new)

        # A match is useful only if there is a unique canonical target.
        unique_targets = {m["folder"] for m in matches}
        if len(unique_targets) == 1:
            redirects[old["folder"]] = next(iter(unique_targets))
        elif len(unique_targets) > 1:
            ambiguous.append((old["folder"], sorted(unique_targets)))

    htaccess = ROOT / ".htaccess"
    existing = htaccess.read_text(encoding="utf-8", errors="ignore") if htaccess.exists() else ""

    lines = [
        BEGIN,
        "# Canonicalize directory index URLs",
        "Redirect 301 /articulos/index.html /articulos/",
        "Redirect 301 /prensa/index.html /prensa/",
        "Redirect 301 /libro/index.html /libro/",
        "Redirect 301 /sobre-mi/index.html /sobre-mi/",
        "Redirect 301 /podcasts/index.html /podcasts/",
        "",
        "# Legacy article URLs",
    ]

    for old, new in sorted(redirects.items()):
        if old != new:
            lines.append(
                f"Redirect 301 /articulos/{old}/ /articulos/{new}/"
            )

    lines.append(END)
    managed = "\n".join(lines)

    pattern = re.compile(
        rf"{re.escape(BEGIN)}.*?{re.escape(END)}",
        flags=re.S,
    )
    if pattern.search(existing):
        updated = pattern.sub(managed, existing)
    else:
        updated = (existing.rstrip() + "\n\n" if existing.strip() else "") + managed + "\n"

    if updated != existing:
        htaccess.write_text(updated, encoding="utf-8")

    print(f"Canonical article folders in sitemap: {len(canon)}")
    print(f"Legacy article folders scanned: {len(legacy)}")
    print(f"301 redirects prepared: {len(redirects)}")
    print(f"Ambiguous matches requiring manual review: {len(ambiguous)}")

    for old, new in sorted(redirects.items()):
        print(f"REDIRECT {old} -> {new}")

    for old, targets in ambiguous:
        print(f"AMBIGUOUS {old} -> {', '.join(targets)}")


if __name__ == "__main__":
    main()
