#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "articulos" / "index.html"
TARGET = "when-ultra-processing-obscures-sustainable-dietary-transitions"

def clean(v: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(v or "")).strip()

def main():
    if not INDEX.exists():
        raise FileNotFoundError("articulos/index.html not found")

    text = INDEX.read_text(encoding="utf-8", errors="ignore")

    print("=" * 72)
    print("STEP 9B — AUDIT RESEARCH INDEX STRUCTURE")
    print("=" * 72)

    print("Target already in index:",
          f"/articulos/{TARGET}/" in text)

    # All internal article links.
    links = re.findall(
        r'href=["\'](?:https://nutreconciencia\.com)?/articulos/([^/"\']+)/?["\']',
        text,
        flags=re.I,
    )
    links = sorted(dict.fromkeys(links))

    print(f"Unique article links found in index: {len(links)}")
    for slug in links[:100]:
        print(" -", slug)

    # Candidate card structures.
    class_names = sorted(set(re.findall(
        r'class=["\']([^"\']*(?:card|article|research|publication)[^"\']*)["\']',
        text,
        flags=re.I,
    )))
    print("\nCandidate classes:")
    for c in class_names[:100]:
        print(" -", c)

    # Containers around known article links.
    target_match = re.search(
        r'(<a\b[^>]*href=["\'](?:https://nutreconciencia\.com)?/articulos/[^"\']+["\'][^>]*>.*?</a>)',
        text,
        flags=re.I | re.S,
    )
    if target_match:
        snippet = clean(target_match.group(1))
        print("\nFirst article-link snippet:")
        print(snippet[:1600])

    # Main structural sections.
    sections = []
    for m in re.finditer(r'<(?:section|div)\b[^>]*class=["\']([^"\']+)["\'][^>]*>', text, re.I):
        cls = m.group(1)
        if re.search(r'article|research|publication|grid|list', cls, re.I):
            sections.append((m.start(), cls))
    print("\nRelevant structural containers:")
    for _, cls in sections[:100]:
        print(" -", cls)

    # JSON-like/metadata sources for current cards.
    metadata_files = sorted(
        str(p.relative_to(ROOT))
        for p in (ROOT / "articulos").glob("*/metadata.json")
    )
    print(f"\nmetadata.json files currently present: {len(metadata_files)}")
    for p in metadata_files[-20:]:
        print(" -", p)

    print("\nREAD-ONLY: no files were modified.")

if __name__ == "__main__":
    main()
