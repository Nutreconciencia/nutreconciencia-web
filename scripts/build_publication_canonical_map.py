#!/usr/bin/env python3
"""
STEP 3 — Build the definitive canonical map for research publications.

READ-ONLY: does not modify sitemap, .htaccess or article pages.

For each duplicate identity group, it proposes one canonical URL using:
1. If exactly one member is already in sitemap -> keep it.
2. Otherwise, if exactly one member is NOT noindex -> propose it.
3. Otherwise -> MANUAL_REVIEW.

It also writes a canonical map CSV/Markdown report so the next migration can
be performed once, instead of generating one redirect version at a time.
"""

from __future__ import annotations

import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
SITEMAP = ROOT / "sitemap.xml"
OUT_CSV = ROOT / "publication_canonical_map.csv"
OUT_MD = ROOT / "publication_canonical_map.md"


def clean(v: str) -> str:
    v = html.unescape(v or "")
    return re.sub(r"\s+", " ", v).strip()


def norm(v: str) -> str:
    v = clean(v).lower()
    v = re.sub(r"[^\w\s]", " ", v, flags=re.UNICODE)
    return re.sub(r"\s+", " ", v).strip()


def extract(pattern: str, text: str) -> str:
    m = re.search(pattern, text, flags=re.I | re.S)
    return clean(m.group(1)) if m else ""


def sitemap_slugs() -> set[str]:
    if not SITEMAP.exists():
        return set()
    text = SITEMAP.read_text(encoding="utf-8", errors="ignore")
    return {
        html.unescape(m.group(1)).strip("/")
        for m in re.finditer(
            r"<loc>\s*https?://nutreconciencia\.com/articulos/([^<\s/]+?)/?\s*</loc>",
            text,
            flags=re.I,
        )
    }


def read_article(folder: Path, sitemap: set[str]) -> dict:
    text = (folder / "index.html").read_text(encoding="utf-8", errors="ignore")
    title = extract(r"<h1[^>]*>(.*?)</h1>", text) or extract(r"<title[^>]*>(.*?)</title>", text)
    canonical = extract(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        text,
    )
    doi = extract(r"""https?://doi\.org/([^"'<\s]+)""", text).rstrip(").,;").lower()
    pmid = extract(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", text)
    noindex = bool(re.search(
        r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex',
        text, flags=re.I
    ))

    meta = {}
    f = folder / "orcid.json"
    if f.exists():
        try:
            meta = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass

    doi = doi or clean(str(meta.get("doi") or "")).lower()
    pmid = pmid or clean(str(meta.get("pmid") or ""))

    return {
        "slug": folder.name,
        "title": title,
        "title_key": norm(title),
        "doi": doi,
        "pmid": pmid,
        "canonical": canonical,
        "sitemap": folder.name in sitemap,
        "noindex": noindex,
    }


def group_articles(articles: list[dict]) -> list[list[dict]]:
    remaining = {a["slug"]: a for a in articles}
    groups: list[list[dict]] = []

    def take_matching(key_name: str):
        keys = defaultdict(list)
        for a in remaining.values():
            if a[key_name]:
                keys[a[key_name]].append(a)
        for key, members in keys.items():
            if len(members) > 1:
                groups.append(members)
                for m in members:
                    remaining.pop(m["slug"], None)

    take_matching("doi")
    take_matching("pmid")
    take_matching("title_key")
    return groups


def propose(members: list[dict]) -> tuple[str, str]:
    sitemap_members = [m for m in members if m["sitemap"]]
    if len(sitemap_members) == 1:
        return sitemap_members[0]["slug"], "SITEMAP_CANONICAL"

    visible = [m for m in members if not m["noindex"]]
    if len(visible) == 1:
        return visible[0]["slug"], "NON_NOINDEX_CANONICAL"

    return "", "MANUAL_REVIEW"


def main():
    sitemap = sitemap_slugs()
    articles = []

    for folder in sorted(ART.iterdir()):
        if folder.is_dir() and (folder / "index.html").exists():
            articles.append(read_article(folder, sitemap))

    groups = group_articles(articles)

    rows = []
    for i, members in enumerate(groups, 1):
        canonical, reason = propose(members)
        for m in members:
            rows.append({
                "group": i,
                "identity": m["doi"] or m["pmid"] or m["title_key"],
                "proposed_canonical": canonical,
                "proposal_reason": reason,
                "slug": m["slug"],
                "title": m["title"],
                "doi": m["doi"],
                "pmid": m["pmid"],
                "sitemap": m["sitemap"],
                "noindex": m["noindex"],
                "canonical_url": m["canonical"],
            })

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    counts = defaultdict(int)
    for r in rows:
        counts[r["proposal_reason"]] += 1

    md = [
        "# Definitive publication canonical map",
        "",
        f"- Duplicate groups analysed: **{len(groups)}**",
        f"- Groups proposed from sitemap: **{len({r['group'] for r in rows if r['proposal_reason']=='SITEMAP_CANONICAL'})}**",
        f"- Groups proposed from unique non-noindex page: **{len({r['group'] for r in rows if r['proposal_reason']=='NON_NOINDEX_CANONICAL'})}**",
        f"- Groups requiring manual review: **{len({r['group'] for r in rows if r['proposal_reason']=='MANUAL_REVIEW'})}**",
        "",
    ]

    seen = set()
    for r in rows:
        g = r["group"]
        if g in seen:
            continue
        seen.add(g)
        group_rows = [x for x in rows if x["group"] == g]
        md += [
            f"## Group {g}",
            f"- Identity: `{r['identity']}`",
            f"- Proposed canonical: `{r['proposed_canonical'] or 'MANUAL REVIEW'}`",
            f"- Reason: **{r['proposal_reason']}**",
            "",
        ]
        for x in group_rows:
            flags = []
            if x["sitemap"]:
                flags.append("SITEMAP")
            if x["noindex"]:
                flags.append("NOINDEX")
            md.append(f"- `{x['slug']}` | {x['title']} | {', '.join(flags) or '-'}")
        md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("=" * 72)
    print("STEP 3 — DEFINITIVE CANONICAL MAP")
    print("=" * 72)
    print(f"Duplicate groups analysed: {len(groups)}")
    print("Sitemap canonicals:", len({r['group'] for r in rows if r['proposal_reason']=='SITEMAP_CANONICAL'}))
    print("Non-noindex canonicals:", len({r['group'] for r in rows if r['proposal_reason']=='NON_NOINDEX_CANONICAL'}))
    print("Manual review:", len({r['group'] for r in rows if r['proposal_reason']=='MANUAL_REVIEW'}))
    print(f"\nCreated: {OUT_MD.name}")
    print(f"Created: {OUT_CSV.name}")
    print("\nREAD-ONLY — no website files were modified.")


if __name__ == "__main__":
    main()
