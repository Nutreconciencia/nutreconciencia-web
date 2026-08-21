#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "articulos" / "index.html"
META = ROOT / "articulos" / "when-ultra-processing-obscures-sustainable-dietary-transitions" / "metadata.json"

TARGET = "when-ultra-processing-obscures-sustainable-dietary-transitions"

def clean(v):
    return re.sub(r"\s+", " ", v or "").strip()

def main():
    if not INDEX.exists():
        raise FileNotFoundError("articulos/index.html not found")
    if not META.exists():
        raise FileNotFoundError("metadata.json for target paper not found")

    text = INDEX.read_text(encoding="utf-8", errors="ignore")
    data = json.loads(META.read_text(encoding="utf-8"))

    title = clean(data.get("title"))
    year = clean(data.get("year"))
    journal = clean(data.get("journal")) or "Publicación científica"

    old_pattern = re.compile(
        r'<article\s+class="paper-cover"\s+data-year="'
        + re.escape(year)
        + r'"\s+data-title="'
        + re.escape(title.lower())
        + r'">\s*<a\s+href="/articulos/'
        + re.escape(TARGET)
        + r'/">.*?</a>\s*</article>',
        re.I | re.S,
    )

    new_card = (
        '<a class="paper-cover" '
        f'data-year="{escape(year, quote=True)}" '
        f'data-title="{escape(title.lower(), quote=True)}" '
        f'href="/articulos/{TARGET}/">'
        f'<div class="paper-year">{escape(year)}</div>'
        f'<h3>{escape(title)}</h3>'
        f'<div class="paper-journal">{escape(journal)}</div>'
        '</a>'
    )

    if not old_pattern.search(text):
        raise RuntimeError("The incorrectly structured new card was not found")

    updated = old_pattern.sub(new_card, text, count=1)

    # Verify exact expected structure and uniqueness.
    if updated.count(f'href="/articulos/{TARGET}/"') != 1:
        raise RuntimeError("Target card does not occur exactly once after replacement")

    if f'<a class="paper-cover" data-year="{year}"' not in updated:
        raise RuntimeError("New card does not use the existing paper-cover anchor structure")

    if '<article class="paper-cover"' in updated:
        raise RuntimeError("Old incorrect article.paper-cover structure remains")

    INDEX.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("STEP 9B FIX — MATCH EXISTING PAPER CARD STRUCTURE")
    print("=" * 72)
    print("Target:", TARGET)
    print("Card structure: MATCHED TO EXISTING .paper-cover ANCHORS")
    print("Target card occurrences: 1")
    print("Existing cards preserved.")
    print("Only articulos/index.html was modified.")

if __name__ == "__main__":
    main()
