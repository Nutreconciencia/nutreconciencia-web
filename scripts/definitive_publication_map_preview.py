#!/usr/bin/env python3
"""
STEP 4 — Preview the definitive canonical map for all duplicate publication
groups.

READ-ONLY. No sitemap, .htaccess or article pages are modified.

Canonical selection:
1. Existing unique sitemap canonical.
2. Explicit manual decisions for the 15 groups that had no sitemap canonical.
3. Unique non-noindex candidate (10 groups).

The script writes:
- definitive_publication_map.csv
- definitive_publication_map.md

These files are a PREVIEW for the final migration.
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
OUT_CSV = ROOT / "definitive_publication_map.csv"
OUT_MD = ROOT / "definitive_publication_map.md"

MANUAL_CANONICALS = {
    "10.1080/15502783.2026.2674220":
        "acute-beetroot-juice-ingestion-fails-to-improve-sprint-performance-and-neuromuscular-function-in-tra",
    "10.3390/nu13093174":
        "adherence-to-mediterranean-diet-alcohol-consumption-and-emotional-eating-in-spanish-university-stude",
    "10.3389/fnut.2025.1622160":
        "commentary-the-energy-model-of-insulin-resistance-a-unifying-theory-linking-seed-oils-to-metabolic-d",
    "10.3390/app16157696":
        "determinants-of-adherence-and-their-relationship-with-clinical-response-to-a-vegan-mediterranean-die",
    "10.1016/j.cdnut.2025.106498":
        "examining-the-impact-of-isocaloric-substitution-of-animal-protein-with-plant-protein-all-cause-cardi",
    "10.1038/s41598-025-85307-5":
        "feasibility-and-potential-effect-of-a-pilot-blended-digital-behavior-change-intervention-promoting-s",
    "10.31219/osf.io/d9pm3":
        "feasibility-of-a-blended-digital-behavior-change-intervention-promoting-sustainable-diets-over-a-yea",
    "10.1371/journal.pone.0351122":
        "higher-dietary-polyphenol-intake-is-associated-with-reduced-pain-sensitivity-and-migraine-related-di",
    "10.1016/j.heliyon.2021.e07186":
        "influence-of-eating-habits-and-alcohol-consumption-on-the-academic-performance-among-a-university-po",
    "10.1007/s00431-025-06298-z":
        "is-greater-adherence-to-the-mediterranean-diet-related-to-higher-health-related-quality-of-life-amon",
    "10.1371/journal.pdig.0001113":
        "longitudinal-changes-in-motivational-determinants-of-sustainable-diets-during-a-pilot-blended-digita",
    "10.3390/nu17040629":
        "orthorexia-nervosa-prevalence-among-spanish-university-students-and-its-effects-on-cardiometabolic-h",
    "10.20944/preprints202010.0325.v1":
        "physical-and-psychological-effects-related-to-food-habits-and-lifestyle-changes-derived-from-covid-1",
    "10.1007/s13668-026-00754-4":
        "protein-paradox-protein-quality-based-on-amino-acids-composition-is-poorly-associated-with-health-ou",
    "10.3390/nu16203492":
        "validation-of-the-modified-yale-food-addiction-scale-20-myfas-20-in-spanish-university-students",
}


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
            text, flags=re.I
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

    for key_name in ("doi", "pmid", "title_key"):
        buckets = defaultdict(list)
        for a in remaining.values():
            if a[key_name]:
                buckets[a[key_name]].append(a)

        for members in buckets.values():
            if len(members) > 1:
                groups.append(members)
                for m in members:
                    remaining.pop(m["slug"], None)

    return groups


def group_identity(members: list[dict]) -> str:
    for m in members:
        if m["doi"]:
            return m["doi"]
    for m in members:
        if m["pmid"]:
            return f"PMID:{m['pmid']}"
    return f"TITLE:{members[0]['title_key']}"


def choose_canonical(members: list[dict]) -> tuple[str, str]:
    identity = group_identity(members)

    # 1. Explicit manual decisions for the 15 review groups.
    if identity in MANUAL_CANONICALS:
        slug = MANUAL_CANONICALS[identity]
        if any(m["slug"] == slug for m in members):
            return slug, "MANUAL_DECISION"

    # 2. Existing unique sitemap canonical.
    sitemap_members = [m for m in members if m["sitemap"]]
    if len(sitemap_members) == 1:
        return sitemap_members[0]["slug"], "SITEMAP_CANONICAL"

    # 3. Unique non-noindex candidate.
    visible = [m for m in members if not m["noindex"]]
    if len(visible) == 1:
        return visible[0]["slug"], "NON_NOINDEX_CANONICAL"

    return "", "UNRESOLVED"


def main():
    sitemap = sitemap_slugs()
    articles = []

    for folder in sorted(ART.iterdir()):
        if folder.is_dir() and (folder / "index.html").exists():
            articles.append(read_article(folder, sitemap))

    groups = group_articles(articles)

    rows = []
    unresolved = []

    for group_number, members in enumerate(groups, 1):
        identity = group_identity(members)
        canonical, reason = choose_canonical(members)

        if not canonical:
            unresolved.append(identity)

        for m in members:
            target_url = (
                f"https://nutreconciencia.com/articulos/{canonical}/"
                if canonical else ""
            )
            rows.append({
                "group": group_number,
                "identity": identity,
                "canonical_slug": canonical,
                "canonical_url": target_url,
                "decision": reason,
                "slug": m["slug"],
                "title": m["title"],
                "doi": m["doi"],
                "pmid": m["pmid"],
                "sitemap": m["sitemap"],
                "noindex": m["noindex"],
                "current_canonical": m["canonical"],
                "is_canonical": m["slug"] == canonical,
                "redirect_required": bool(canonical and m["slug"] != canonical),
            })

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(f, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)

    md = [
        "# Definitive publication map — PREVIEW",
        "",
        f"- Duplicate groups: **{len(groups)}**",
        f"- Manual decisions applied: **15 configured**",
        f"- Unresolved groups: **{len(unresolved)}**",
        "",
        "## Summary",
        "",
        "| Group | Identity | Canonical | Decision |",
        "|---:|---|---|---|",
    ]

    for g in range(1, len(groups) + 1):
        gr = [r for r in rows if r["group"] == g]
        first = gr[0]
        md.append(
            f"| {g} | `{first['identity']}` | "
            f"`{first['canonical_slug'] or 'UNRESOLVED'}` | {first['decision']} |"
        )

    md += ["", "## Redirect preview", ""]
    for r in rows:
        if r["redirect_required"]:
            md.append(
                f"- `/articulos/{r['slug']}/` → `{r['canonical_url']}`"
            )
            md.append(
                f"- `/articulos/{r['slug']}/index.html` → `{r['canonical_url']}`"
            )

    if unresolved:
        md += ["", "## UNRESOLVED GROUPS", ""]
        for identity in unresolved:
            md.append(f"- `{identity}`")

    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("=" * 72)
    print("STEP 4 — DEFINITIVE PUBLICATION MAP PREVIEW")
    print("=" * 72)
    print(f"Duplicate groups: {len(groups)}")
    print("Manual decisions configured: 15")
    print(f"Unresolved groups: {len(unresolved)}")
    print(f"CSV: {OUT_CSV.name}")
    print(f"Markdown: {OUT_MD.name}")
    if unresolved:
        print("\nUNRESOLVED:")
        for u in unresolved:
            print(u)
    else:
        print("\nAll 51 duplicate groups have a canonical proposal.")
    print("\nREAD-ONLY — no website files were modified.")


if __name__ == "__main__":
    main()
