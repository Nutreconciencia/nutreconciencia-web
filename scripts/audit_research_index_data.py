#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "articulos" / "index.html"

PATTERNS = [
    r'<script\b[^>]*src=["\']([^"\']+)["\'][^>]*>',
    r'<script\b[^>]*>(.*?)</script>',
    r'journal-grid',
    r'const\s+\w+\s*=\s*\[',
    r'let\s+\w+\s*=\s*\[',
    r'var\s+\w+\s*=\s*\[',
    r'fetch\(["\']([^"\']+)',
    r'localStorage',
    r'data-[\w-]+=["\'][^"\']+',
]

def main():
    if not INDEX.exists():
        raise FileNotFoundError("articulos/index.html not found")

    text = INDEX.read_text(encoding="utf-8", errors="ignore")

    print("=" * 72)
    print("STEP 9B — AUDIT RESEARCH INDEX DATA SOURCE")
    print("=" * 72)

    # Show script src files.
    srcs = re.findall(PATTERNS[0], text, flags=re.I | re.S)
    print(f"Script src references: {len(srcs)}")
    for src in srcs:
        print(" -", src)

    # Show inline scripts with useful clues, but truncate safely.
    inline = re.findall(PATTERNS[1], text, flags=re.I | re.S)
    print(f"Inline script blocks: {len(inline)}")
    for i, block in enumerate(inline, 1):
        if any(token in block.lower() for token in (
            "journal-grid", "fetch(", "const ", "let ", "var ",
            "json", "article", "publication", "research"
        )):
            compact = re.sub(r"\s+", " ", block).strip()
            print(f"\n--- inline script {i} ---")
            print(compact[:5000])

    # Data attributes around journal-grid.
    m = re.search(
        r'<[^>]+class=["\'][^"\']*journal-grid[^"\']*["\'][^>]*>',
        text, flags=re.I | re.S
    )
    print("\nJournal-grid opening tag:")
    print(m.group(0) if m else "NOT FOUND")

    # Forms/selects and IDs in the research controls.
    controls = re.findall(
        r'<(?:input|select|button|form)\b[^>]*>',
        text, flags=re.I | re.S
    )
    print(f"\nResearch control elements found: {len(controls)}")
    for tag in controls[:80]:
        if any(k in tag.lower() for k in ("research", "journal", "search", "filter", "sort", "data-")):
            print(" -", tag)

    print("\nREAD-ONLY: no files modified.")

if __name__ == "__main__":
    main()
