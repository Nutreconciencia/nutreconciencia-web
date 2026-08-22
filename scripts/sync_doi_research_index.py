#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "articulos" / "index.html"
ART = ROOT / "articulos"

def clean(v):
    return re.sub(r"\s+", " ", v or "").strip()

def year_num(v):
    m = re.search(r"\b(20\d{2})\b", v or "")
    return int(m.group(1)) if m else 0

def build_card(slug, data):
    title = clean(data.get("title"))
    year = clean(data.get("year"))
    journal = clean(data.get("journal")) or "Scientific publication"
    publisher = clean(data.get("publisher"))

    publisher_html = (
        f'<div class="paper-cover-publisher">{escape(publisher)}</div>'
        if publisher else ""
    )

    return (
        f'<a class="paper-cover" data-year="{escape(year, quote=True)}" '
        f'data-title="{escape(title.lower(), quote=True)}" '
        f'href="/articulos/{escape(slug)}/">'
        f'<div class="paper-cover-head">'
        '<div class="paper-cover-kicker">SCIENTIFIC PAPER</div>'
        f'<div class="paper-cover-journal">{escape(journal)}</div>'
        f'{publisher_html}'
        f'<div class="paper-cover-issue">{escape(journal)} · {escape(year)}</div>'
        '</div>'
        '<div class="paper-cover-body">'
        f'<div class="paper-cover-title">{escape(title)}</div>'
        '<div class="paper-cover-type">OPEN THE SCIENTIFIC SUMMARY ↗</div>'
        '</div>'
        '</a>'
    )

def find_paper_grid(text):
    opening = re.search(
        r'<div[^>]*class=["\'][^"\']*\bjournal-grid\b[^"\']*["\'][^>]*id=["\']paperGrid["\'][^>]*>',
        text, re.I | re.S
    )
    if not opening:
        # allow id before class as well
        opening = re.search(
            r'<div[^>]*id=["\']paperGrid["\'][^>]*class=["\'][^"\']*\bjournal-grid\b[^"\']*["\'][^>]*>',
            text, re.I | re.S
        )
    if not opening:
        raise RuntimeError("paperGrid not found in articulos/index.html")

    start = opening.end()
    pos = start
    depth = 1
    tag_re = re.compile(r"</?div\b[^>]*>", re.I)

    while True:
        m = tag_re.search(text, pos)
        if not m:
            raise RuntimeError("Could not find closing tag for #paperGrid")
        tag = m.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return start, m.start()
        else:
            depth += 1
        pos = m.end()

def extract_existing_slugs(inner):
    return set(re.findall(
        r'href=["\'](?:https://nutreconciencia\.com)?/articulos/([^/"\']+)/["\']',
        inner, re.I
    ))

def main():
    if not INDEX.exists():
        raise FileNotFoundError(INDEX)

    text = INDEX.read_text(encoding="utf-8", errors="ignore")
    start, end = find_paper_grid(text)
    inner = text[start:end]
    existing = extract_existing_slugs(inner)

    candidates = []
    for meta_path in sorted(ART.glob("*/metadata.json")):
        slug = meta_path.parent.name
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"SKIP {slug}: invalid metadata.json ({exc})")
            continue

        if not clean(data.get("doi")):
            continue
        if slug in existing:
            continue
        if not clean(data.get("title")):
            print(f"SKIP {slug}: missing title")
            continue
        if not clean(data.get("year")):
            print(f"SKIP {slug}: missing year")
            continue

        candidates.append((slug, data))

    candidates.sort(
        key=lambda x: (-year_num(x[1].get("year")), clean(x[1].get("title")).lower())
    )

    if not candidates:
        print("=" * 72)
        print("RESEARCH INDEX SYNC — NO MISSING DOI CARDS")
        print("=" * 72)
        print("All DOI publication cards are already present.")
        return

    cards = "\n".join(build_card(slug, data) for slug, data in candidates)
    updated = text[:start] + "\n" + cards + "\n" + inner + text[end:]

    for slug, data in candidates:
        href = f'/articulos/{slug}/'
        if updated.count(href) != 1:
            raise RuntimeError(f"{slug}: expected exactly one card after insertion")
        if f'<a class="paper-cover" data-year="{clean(data.get("year"))}"' not in updated:
            raise RuntimeError(f"{slug}: editorial paper-cover structure not found")

    INDEX.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("RESEARCH INDEX SYNC — ALL DOI PUBLICATIONS")
    print("=" * 72)
    print("Existing cards preserved.")
    print("New DOI cards inserted:", len(candidates))
    for slug, data in candidates:
        print(
            f" - {clean(data.get('year'))} | "
            f"{clean(data.get('title'))} | "
            f"{clean(data.get('journal')) or 'Scientific publication'}"
        )
    print("#paperGrid structure preserved.")
    print("Only articulos/index.html modified.")

if __name__ == "__main__":
    main()
