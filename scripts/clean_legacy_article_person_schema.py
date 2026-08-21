#!/usr/bin/env python3
"""
STEP 5C — Clean legacy standalone Person JSON-LD from canonical article pages.

Keeps:
- ScholarlyArticle JSON-LD
- nested author Person objects inside ScholarlyArticle

Removes only standalone top-level JSON-LD scripts whose root object is:
  "@type": "Person"
and whose @id is:
  https://nutreconciencia.com/#person

It uses the definitive publication map and changes only the 51 canonical pages.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "definitive_publication_map.csv"
ART = ROOT / "articulos"

TARGET_ID = "https://nutreconciencia.com/#person"

SCRIPT_RE = re.compile(
    r'<script\b(?P<attrs>[^>]*)type=["\']application/ld\+json["\'](?P<attrs2>[^>]*)>'
    r'(?P<body>.*?)</script>',
    flags=re.I | re.S,
)

def is_standalone_person(attrs: str, body: str) -> bool:
    # Preserve the legacy block only if it is not a standalone Person matching
    # our canonical identity.
    try:
        data = json.loads(body.strip())
    except Exception:
        return False

    if not isinstance(data, dict):
        return False

    typ = data.get("@type")
    person_id = data.get("@id")

    if typ == "Person" and person_id == TARGET_ID:
        return True

    # Older pages used data-schema="person-miguel".
    if typ == "Person" and re.search(r'data-schema=["\']person-miguel["\']', attrs, re.I):
        return True

    return False


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
        raise RuntimeError(
            f"Expected 51 canonical pages, found {len(canonical_rows)}"
        )

    modified = 0
    removed_blocks = 0
    remaining_old = []

    for row in canonical_rows:
        slug = (row.get("slug") or "").strip()
        page = ART / slug / "index.html"
        if not page.exists():
            raise FileNotFoundError(page)

        text = page.read_text(encoding="utf-8", errors="ignore")
        count_before = len(text)

        def repl(match: re.Match) -> str:
            nonlocal removed_blocks
            attrs = (match.group("attrs") or "") + (match.group("attrs2") or "")
            body = match.group("body") or ""
            if is_standalone_person(attrs, body):
                removed_blocks += 1
                return ""
            return match.group(0)

        updated = SCRIPT_RE.sub(repl, text)

        if updated != text:
            page.write_text(updated, encoding="utf-8")
            modified += 1

        # Detect any remaining standalone Person block for reporting.
        for match in SCRIPT_RE.finditer(updated):
            attrs = (match.group("attrs") or "") + (match.group("attrs2") or "")
            body = match.group("body") or ""
            if is_standalone_person(attrs, body):
                remaining_old.append(slug)
                break

    if remaining_old:
        raise RuntimeError(
            "Standalone Person schema still present in: "
            + ", ".join(sorted(set(remaining_old)))
        )

    print("=" * 72)
    print("STEP 5C — LEGACY PERSON SCHEMA CLEANUP")
    print("=" * 72)
    print(f"Canonical article pages checked: {len(canonical_rows)}")
    print(f"Pages modified: {modified}")
    print(f"Standalone Person blocks removed: {removed_blocks}")
    print("Nested author Person objects were preserved.")
    print("Homepage /sobre-mi/ Person schema was not modified.")
    print("ScholarlyArticle schema was not modified.")

if __name__ == "__main__":
    main()
