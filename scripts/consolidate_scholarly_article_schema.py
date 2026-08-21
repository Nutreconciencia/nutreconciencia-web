#!/usr/bin/env python3
"""
STEP 5D — Consolidate ScholarlyArticle JSON-LD on the 51 canonical pages.

Goal:
- exactly ONE top-level JSON-LD block for ScholarlyArticle per canonical page;
- preserve existing rich article data when present;
- merge DOI/PMID/date/journal/description/author data from existing blocks;
- force Miguel López Moreno's author identity to the canonical Person @id;
- do not modify legacy article pages, sitemap.xml, .htaccess, home, or /sobre-mi/.

The script intentionally does not invent missing metadata.
"""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "definitive_publication_map.csv"
ART = ROOT / "articulos"

SCHEMA_START = '<script type="application/ld+json"'
SCHEMA_RE = re.compile(
    r'<script\b(?P<attrs>[^>]*)type=["\']application/ld\+json["\'](?P<attrs2>[^>]*)>'
    r'(?P<body>.*?)</script>',
    re.I | re.S,
)

PERSON_ID = "https://nutreconciencia.com/#person"
SCHEMA_ID = "nutreconciencia-scholarly-article-schema"


def clean(v: Any) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(v))).strip()


def parse_json(body: str) -> Any:
    try:
        return json.loads(body.strip())
    except Exception:
        return None


def is_scholarly(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    typ = obj.get("@type")
    if isinstance(typ, list):
        return "ScholarlyArticle" in typ
    return typ == "ScholarlyArticle"


def extract_existing_scholarly(text: str) -> list[tuple[re.Match, dict]]:
    found = []
    for match in SCHEMA_RE.finditer(text):
        obj = parse_json(match.group("body"))
        if is_scholarly(obj):
            found.append((match, obj))
    return found


def canonical_url(slug: str, obj_list: list[dict]) -> str:
    for obj in obj_list:
        url = clean(obj.get("url"))
        if url.startswith("https://nutreconciencia.com/articulos/"):
            return url.rstrip("/") + "/"
        main = clean(obj.get("mainEntityOfPage"))
        if main.startswith("https://nutreconciencia.com/articulos/"):
            return main.rstrip("/") + "/"
    return f"https://nutreconciencia.com/articulos/{slug}/"


def add_author(authors: list[Any]) -> list[Any]:
    out = []
    miguel_found = False

    for a in authors:
        if isinstance(a, dict):
            name = clean(a.get("name"))
            aid = clean(a.get("@id"))
            if name.lower() == "miguel lópez moreno" or aid == PERSON_ID:
                if not miguel_found:
                    out.append({
                        "@type": "Person",
                        "@id": PERSON_ID,
                        "name": "Miguel López Moreno"
                    })
                    miguel_found = True
                continue
        out.append(a)

    if not miguel_found:
        out.append({
            "@type": "Person",
            "@id": PERSON_ID,
            "name": "Miguel López Moreno"
        })

    return out


def merge_schemas(slug: str, existing: list[dict], row: dict) -> dict:
    primary = max(existing, key=lambda x: len(json.dumps(x, ensure_ascii=False)))

    merged = dict(primary)

    # Canonical basics.
    url = canonical_url(slug, existing)
    merged["@context"] = "https://schema.org"
    merged["@type"] = "ScholarlyArticle"
    merged["@id"] = url.rstrip("/") + "/#article"
    merged["url"] = url

    # Headline.
    headline = clean(merged.get("headline"))
    if not headline:
        headline = clean(row.get("title"))
    if headline:
        merged["headline"] = headline

    # Merge common scalar metadata from all blocks.
    for key in ("datePublished", "dateModified", "description"):
        if not clean(merged.get(key)):
            for obj in existing:
                val = clean(obj.get(key))
                if val:
                    merged[key] = val
                    break

    # Merge publisher / journal.
    if not merged.get("publisher") and not merged.get("isPartOf"):
        for obj in existing:
            if obj.get("publisher"):
                merged["publisher"] = obj["publisher"]
                break
            if obj.get("isPartOf"):
                merged["isPartOf"] = obj["isPartOf"]
                break

    # If page metadata contains a visible publisher/journal and existing schema
    # lacks a journal, use the article's explicit metadata markers only.
    if not merged.get("isPartOf"):
        journal_match = re.search(
            r'<span[^>]+class=["\'][^"\']*\bpill\b[^"\']*["\'][^>]*>\s*([^<]+?)\s*</span>',
            text_cache[slug],
            re.I | re.S,
        )
        if journal_match:
            journal = clean(journal_match.group(1))
            if journal and journal.lower() not in {"doi", "pubmed"}:
                merged["isPartOf"] = {
                    "@type": "Periodical",
                    "name": journal
                }

    # Merge sameAs URLs from all schema blocks and row metadata.
    same_as: list[str] = []
    for obj in existing:
        vals = obj.get("sameAs", [])
        if isinstance(vals, str):
            vals = [vals]
        if isinstance(vals, list):
            for v in vals:
                v = clean(v)
                if v and v not in same_as:
                    same_as.append(v)

    doi = clean(row.get("doi"))
    pmid = clean(row.get("pmid"))
    if doi:
        u = f"https://doi.org/{doi}"
        if u not in same_as:
            same_as.append(u)
    if pmid:
        u = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        if u not in same_as:
            same_as.append(u)

    if same_as:
        merged["sameAs"] = same_as

    # Authors from all blocks, de-duplicated by id/name, then force Miguel.
    authors: list[Any] = []
    for obj in existing:
        vals = obj.get("author", [])
        if isinstance(vals, dict):
            vals = [vals]
        if isinstance(vals, list):
            authors.extend(vals)

    dedup = []
    seen = set()
    for a in authors:
        if isinstance(a, dict):
            key = clean(a.get("@id")) or clean(a.get("name")).lower()
            if key:
                if key in seen:
                    continue
                seen.add(key)
            dedup.append(a)
        else:
            key = clean(a).lower()
            if key and key not in seen:
                seen.add(key)
                dedup.append(a)

    merged["author"] = add_author(dedup)

    # Helpful relation: article is about the same Person only if an existing
    # schema already used it. Otherwise don't invent it.
    if "about" in merged and isinstance(merged["about"], dict):
        if clean(merged["about"].get("@id")) == PERSON_ID:
            merged["about"] = {
                "@type": "Person",
                "@id": PERSON_ID,
                "name": "Miguel López Moreno"
            }

    return merged


def render_schema(obj: dict) -> str:
    return (
        f'<script type="application/ld+json" id="{SCHEMA_ID}">\n'
        + json.dumps(obj, ensure_ascii=False, indent=2)
        + "\n</script>"
    )


def replace_all_scholarly(text: str, replacement: str) -> str:
    matches = [m for m in SCHEMA_RE.finditer(text) if is_scholarly(parse_json(m.group("body")))]
    if not matches:
        head = re.search(r"</head>", text, re.I)
        if not head:
            raise RuntimeError("No </head> found")
        return text[:head.start()] + replacement + "\n" + text[head.start():]

    first = matches[0]
    out = text[:first.start()] + replacement + text[first.end():]

    # Remove remaining scholarly blocks using original positions from the
    # text after first replacement; do a second regex pass.
    out = re.sub(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>.*?</script>',
        lambda m: "" if is_scholarly(parse_json(m.group(0)[m.group(0).find(">")+1:m.group(0).rfind("</script>")])) else m.group(0),
        out,
        flags=re.I | re.S,
    )
    # The previous lambda cannot reliably recover if formatting changed; make
    # a safer final pass based on JSON bodies.
    while True:
        changed = False
        parts = []
        last = 0
        for m in SCHEMA_RE.finditer(out):
            obj = parse_json(m.group("body"))
            parts.append(out[last:m.start()])
            if is_scholarly(obj):
                # Keep exactly the first generated block.
                if not any(SCHEMA_ID in p for p in parts):
                    parts.append(m.group(0))
                else:
                    changed = True
                    parts.append("")
            else:
                parts.append(m.group(0))
            last = m.end()
        parts.append(out[last:])
        new_out = "".join(parts)
        if not changed:
            return new_out
        out = new_out


# Cache page source for journal extraction.
text_cache: dict[str, str] = {}


def main():
    if not MAP.exists():
        raise FileNotFoundError("definitive_publication_map.csv not found")

    with MAP.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    canonical_rows = [
        r for r in rows
        if (r.get("is_canonical") or "").strip().lower() == "true"
    ]

    if len(canonical_rows) != 51:
        raise RuntimeError(f"Expected 51 canonical pages, found {len(canonical_rows)}")

    modified = 0
    total_existing_blocks = 0

    for row in canonical_rows:
        slug = clean(row.get("slug"))
        page = ART / slug / "index.html"
        if not page.exists():
            raise FileNotFoundError(page)

        text = page.read_text(encoding="utf-8", errors="ignore")
        text_cache[slug] = text

        found = extract_existing_scholarly(text)

        # There should normally be at least one because STEP 5B already ran,
        # but create one safely if missing.
        if not found:
            found = [(None, {
                "@context": "https://schema.org",
                "@type": "ScholarlyArticle"
            })]

        existing = [obj for _, obj in found]
        total_existing_blocks += len(existing)

        merged = merge_schemas(slug, existing, row)
        replacement = render_schema(merged)

        if found[0][0] is None:
            marker = re.search(r"</head>", text, re.I)
            updated = text[:marker.start()] + replacement + "\n" + text[marker.start():]
        else:
            # Remove all existing ScholarlyArticle blocks, then insert exactly
            # one at the location of the first.
            first_match = found[0][0]
            tmp = text[:first_match.start()] + replacement + text[first_match.end():]

            # Remove any additional scholarly blocks by scanning the new text
            # while protecting our new block by its exact id.
            chunks = []
            last = 0
            generated_seen = False
            for m in SCHEMA_RE.finditer(tmp):
                obj = parse_json(m.group("body"))
                chunks.append(tmp[last:m.start()])
                if is_scholarly(obj):
                    if SCHEMA_ID in m.group("attrs") + m.group("attrs2"):
                        if not generated_seen:
                            chunks.append(m.group(0))
                            generated_seen = True
                        else:
                            chunks.append("")
                    else:
                        # Any older scholarly block is removed.
                        chunks.append("")
                else:
                    chunks.append(m.group(0))
                last = m.end()
            chunks.append(tmp[last:])
            updated = "".join(chunks)

        if updated != text:
            page.write_text(updated, encoding="utf-8")
            modified += 1

    print("=" * 72)
    print("STEP 5D — SCHOLARLYARTICLE CONSOLIDATION")
    print("=" * 72)
    print(f"Canonical article pages processed: {len(canonical_rows)}")
    print(f"Existing ScholarlyArticle blocks before merge: {total_existing_blocks}")
    print(f"Pages modified: {modified}")
    print("Exactly one generated ScholarlyArticle block per canonical page.")
    print("Miguel author identity forced to https://nutreconciencia.com/#person")
    print("No legacy pages, sitemap.xml, or .htaccess modified.")


if __name__ == "__main__":
    main()
