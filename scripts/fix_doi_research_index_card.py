#!/usr/bin/env python3
from __future__ import annotations
import json, re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "articulos" / "index.html"
TARGET = "when-ultra-processing-obscures-sustainable-dietary-transitions"
META = ROOT / "articulos" / TARGET / "metadata.json"

def clean(v):
    return re.sub(r"\s+", " ", v or "").strip()

def build_card(data):
    title = clean(data.get("title"))
    year = clean(data.get("year"))
    journal = clean(data.get("journal")) or "Scientific publication"
    publisher = clean(data.get("publisher"))
    pub = f'<div class="paper-cover-publisher">{escape(publisher)}</div>' if publisher else ""
    return (
        f'<a class="paper-cover" data-year="{escape(year, quote=True)}" '
        f'data-title="{escape(title.lower(), quote=True)}" '
        f'href="/articulos/{TARGET}/">'
        f'<div class="paper-cover-head">'
        '<div class="paper-cover-kicker">SCIENTIFIC PAPER</div>'
        f'<div class="paper-cover-journal">{escape(journal)}</div>'
        f'{pub}'
        f'<div class="paper-cover-issue">{escape(journal)} · {escape(year)}</div>'
        '</div>'
        '<div class="paper-cover-body">'
        f'<div class="paper-cover-title">{escape(title)}</div>'
        '<div class="paper-cover-type">OPEN THE SCIENTIFIC SUMMARY ↗</div>'
        '</div></a>'
    )

def main():
    text = INDEX.read_text(encoding="utf-8", errors="ignore")
    data = json.loads(META.read_text(encoding="utf-8"))
    href = f'/articulos/{TARGET}/'
    n = text.count(href)
    if n != 1:
        raise RuntimeError(f"Expected exactly one target href; found {n}")

    # Match the whole anchor containing the target href, regardless of its old structure.
    rx = re.compile(
        r'<a\b(?=[^>]*href=["\']' + re.escape(href) + r'["\'])[^>]*>.*?</a>',
        re.I | re.S
    )
    m = rx.search(text)
    if not m:
        raise RuntimeError("Target href found, but enclosing anchor not found")

    updated = text[:m.start()] + build_card(data) + text[m.end():]

    if updated.count(href) != 1:
        raise RuntimeError("Target card uniqueness failed")
    if 'class="paper-cover"' not in updated[m.start():m.start()+400]:
        raise RuntimeError("paper-cover structure verification failed")

    INDEX.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("FIX DOI RESEARCH INDEX — ROBUST CARD REPLACEMENT V2")
    print("=" * 72)
    print("Target:", TARGET)
    print("Target href occurrences before:", n)
    print("Target href occurrences after: 1")
    print("Editorial .paper-cover structure: PASS")
    print("Scientific-paper CTA: PASS")
    print("Only articulos/index.html modified.")

if __name__ == "__main__":
    main()

