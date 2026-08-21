#!/usr/bin/env python3
"""
STEP 2 — Group research article folders into publication identities.

READ-ONLY: this script does NOT modify the website.

For every /articulos/<slug>/index.html it extracts:
- title
- canonical
- DOI
- PMID
- ORCID work id
- sitemap membership
- noindex

It then groups folders by DOI first, PMID second, and normalized title only
when neither DOI nor PMID is available.

For each group it proposes the canonical folder:
1. Prefer the folder already present in sitemap.xml.
2. If exactly one sitemap member exists, that is the proposed canonical.
3. If none exists, mark the group "NO_SITEMAP_CANONICAL".
4. If >1 sitemap members exist, mark "MULTIPLE_SITEMAP_CANONICALS".

The script writes:
- publication_groups_report.md
- publication_groups.csv

and prints a concise summary to Actions.
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
REPORT_MD = ROOT / "publication_groups_report.md"
REPORT_CSV = ROOT / "publication_groups.csv"


def clean(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_title(value: str) -> str:
    value = clean(value).lower()
    value = value.replace("‐", "-").replace("–", "-").replace("—", "-")
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


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


def article_meta(folder: Path, sitemap: set[str]) -> dict:
    page = folder / "index.html"
    text = page.read_text(encoding="utf-8", errors="ignore")

    title = extract(r"<h1[^>]*>(.*?)</h1>", text)
    if not title:
        title = extract(r"<title[^>]*>(.*?)</title>", text)

    canonical = extract(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        text,
    )
    doi = extract(r"""https?://doi\.org/([^"'<\s]+)""", text).rstrip(").,;").lower()
    pmid = extract(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", text)

    noindex = bool(
        re.search(
            r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex',
            text,
            flags=re.I,
        )
    )

    meta = {}
    meta_file = folder / "orcid.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    doi = doi or clean(str(meta.get("doi") or "")).lower()
    pmid = pmid or clean(str(meta.get("pmid") or ""))
    orcid_work_id = clean(
        str(
            meta.get("orcid_work_id")
            or meta.get("put_code")
            or meta.get("orcid_put_code")
            or ""
        )
    )

    return {
        "slug": folder.name,
        "title": title,
        "title_key": normalize_title(title),
        "doi": doi,
        "pmid": pmid,
        "orcid_work_id": orcid_work_id,
        "canonical": canonical,
        "sitemap": folder.name in sitemap,
        "noindex": noindex,
    }


def make_groups(articles: list[dict]) -> list[dict]:
    groups = []
    used: set[str] = set()

    # Strongest identity first: DOI, then PMID, then normalized title
    buckets = []
    for key_name, label in [
        ("doi", "DOI"),
        ("pmid", "PMID"),
        ("title_key", "TITLE"),
    ]:
        mapping = defaultdict(list)
        for a in articles:
            if a["slug"] in used:
                continue
            key = a[key_name]
            if key:
                mapping[key].append(a)
        for key, members in mapping.items():
            if len(members) > 1:
                buckets.append((label, key, members))
                used.update(m["slug"] for m in members)

    for identity_type, identity_key, members in buckets:
        sitemap_members = [m for m in members if m["sitemap"]]
        if len(sitemap_members) == 1:
            status = "CANONICAL_FROM_SITEMAP"
            proposed = sitemap_members[0]["slug"]
        elif len(sitemap_members) == 0:
            status = "NO_SITEMAP_CANONICAL"
            proposed = ""
        else:
            status = "MULTIPLE_SITEMAP_CANONICALS"
            proposed = ""

        groups.append({
            "identity_type": identity_type,
            "identity_key": identity_key,
            "status": status,
            "proposed_canonical": proposed,
            "members": members,
        })

    return groups


def main() -> None:
    sitemap = sitemap_slugs()

    articles = []
    for folder in sorted(ART.iterdir()):
        if folder.is_dir() and (folder / "index.html").exists():
            articles.append(article_meta(folder, sitemap))

    groups = make_groups(articles)

    rows = []
    for g in groups:
        members = g["members"]
        for member in members:
            rows.append({
                "identity_type": g["identity_type"],
                "identity_key": g["identity_key"],
                "status": g["status"],
                "proposed_canonical": g["proposed_canonical"],
                "slug": member["slug"],
                "title": member["title"],
                "doi": member["doi"],
                "pmid": member["pmid"],
                "sitemap": member["sitemap"],
                "noindex": member["noindex"],
                "canonical_url": member["canonical"],
            })

    with REPORT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [
            "identity_type", "identity_key", "status", "proposed_canonical",
            "slug", "title", "doi", "pmid", "sitemap", "noindex", "canonical_url"
        ])
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Publication identity groups",
        "",
        f"- Article folders scanned: **{len(articles)}**",
        f"- Groups with duplicates: **{len(groups)}**",
        f"- Groups with one canonical candidate from sitemap: **{sum(g['status'] == 'CANONICAL_FROM_SITEMAP' for g in groups)}**",
        f"- Groups with no sitemap canonical: **{sum(g['status'] == 'NO_SITEMAP_CANONICAL' for g in groups)}**",
        f"- Groups with multiple sitemap canonicals: **{sum(g['status'] == 'MULTIPLE_SITEMAP_CANONICALS' for g in groups)}**",
        "",
        "## Groups",
        "",
    ]

    for idx, g in enumerate(groups, 1):
        lines += [
            f"### {idx}. {g['identity_type']} — `{g['identity_key']}`",
            f"- Status: **{g['status']}**",
            f"- Proposed canonical: `{g['proposed_canonical'] or 'MANUAL REVIEW'}`",
            "",
        ]
        for m in g["members"]:
            flags = []
            if m["sitemap"]:
                flags.append("SITEMAP")
            if m["noindex"]:
                flags.append("NOINDEX")
            flags_text = ", ".join(flags) if flags else "-"
            lines.append(
                f"- `{m['slug']}` | {m['title']} | {flags_text}"
            )
        lines.append("")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 72)
    print("STEP 2 — PUBLICATION IDENTITY GROUPS")
    print("=" * 72)
    print(f"Article folders scanned: {len(articles)}")
    print(f"Duplicate identity groups: {len(groups)}")
    print(
        "Groups with canonical from sitemap: "
        f"{sum(g['status'] == 'CANONICAL_FROM_SITEMAP' for g in groups)}"
    )
    print(
        "Groups without sitemap canonical: "
        f"{sum(g['status'] == 'NO_SITEMAP_CANONICAL' for g in groups)}"
    )
    print(
        "Groups with multiple sitemap canonicals: "
        f"{sum(g['status'] == 'MULTIPLE_SITEMAP_CANONICALS' for g in groups)}"
    )
    print("")
    print("Reports written:")
    print(f"- {REPORT_MD.name}")
    print(f"- {REPORT_CSV.name}")
    print("")
    print("READ-ONLY — no website files were modified.")


if __name__ == "__main__":
    main()
