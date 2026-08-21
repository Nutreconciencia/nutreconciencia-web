#!/usr/bin/env python3
"""
Install the final article rewrite redirects from the committed
definitive_publication_map.csv.

READ/MODIFY:
- modifies .htaccess only
- does not alter article pages
- does not alter sitemap.xml
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_CSV = ROOT / "definitive_publication_map.csv"
HTACCESS = ROOT / ".htaccess"

BEGIN = "# BEGIN NUTRECONCIENCIA FINAL ARTICLE REWRITE REDIRECTS"
END = "# END NUTRECONCIENCIA FINAL ARTICLE REWRITE REDIRECTS"


def load_redirects() -> list[tuple[str, str]]:
    if not MAP_CSV.exists():
        raise FileNotFoundError(f"Missing {MAP_CSV}")

    pairs: set[tuple[str, str]] = set()

    with MAP_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"slug", "canonical_slug", "redirect_required"}
        if not required.issubset(reader.fieldnames or set()):
            raise RuntimeError(
                f"CSV is missing required columns. Found: {reader.fieldnames}"
            )

        for row in reader:
            old = (row.get("slug") or "").strip()
            new = (row.get("canonical_slug") or "").strip()
            redirect_required = (row.get("redirect_required") or "").strip().lower()

            if redirect_required == "true" and old and new and old != new:
                pairs.add((old, new))

    return sorted(pairs)


def install_block(pairs: list[tuple[str, str]]) -> None:
    existing = HTACCESS.read_text(encoding="utf-8") if HTACCESS.exists() else ""

    # Remove any previous copy of our managed block.
    existing = re.sub(
        re.escape(BEGIN) + r".*?" + re.escape(END),
        "",
        existing,
        flags=re.S,
    ).strip()

    rules = [
        BEGIN,
        "# These explicit RewriteRules run before generic index.html rules.",
        "RewriteEngine On",
        "",
    ]

    for old_slug, new_slug in pairs:
        old_re = re.escape(old_slug)
        rules.append(
            f"RewriteRule ^articulos/{old_re}/index\\.html$ /articulos/{new_slug}/ [R=301,L,NE]"
        )
        rules.append(
            f"RewriteRule ^articulos/{old_re}/$ /articulos/{new_slug}/ [R=301,L,NE]"
        )

    rules.append(END)
    block = "\n".join(rules)

    final = block + "\n\n"
    if existing:
        final += existing + "\n"

    HTACCESS.write_text(final, encoding="utf-8")


def main() -> None:
    pairs = load_redirects()

    if not pairs:
        raise RuntimeError(
            "0 redirect mappings loaded from definitive_publication_map.csv"
        )

    # These two are mandatory smoke tests for the current issue.
    required = {
        (
            "dietary-adaptation-of-non-heme-iron-absorption-in-vegans-a-controlled-trial",
            "iron-absorption",
        ),
        (
            "acute-beetroot-juice-ingestion-fails-to-improve-sprint-performance-and-neuromuscular-funct",
            "acute-beetroot-juice-ingestion-fails-to-improve-sprint-performance-and-neuromuscular-function-in-tra",
        ),
    }

    missing = required - set(pairs)
    if missing:
        raise RuntimeError(f"Mandatory mappings missing: {sorted(missing)}")

    install_block(pairs)

    print("=" * 72)
    print("FINAL ARTICLE REDIRECTS")
    print("=" * 72)
    print(f"Redirect mappings installed: {len(pairs)}")
    print("✓ Iron absorption mapping present")
    print("✓ Acute beetroot mapping present")
    print("✓ /index.html variants handled directly")
    print("Updated: .htaccess")


if __name__ == "__main__":
    main()

