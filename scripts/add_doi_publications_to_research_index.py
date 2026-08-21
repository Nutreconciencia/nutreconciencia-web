#!/usr/bin/env python3
from __future__ import annotations
import json, re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "articulos" / "index.html"
ART = ROOT / "articulos"

def clean(v):
    return re.sub(r"\s+", " ", v or "").strip()

def main():
    if not INDEX.exists():
        raise FileNotFoundError("articulos/index.html not found")

    text = INDEX.read_text(encoding="utf-8", errors="ignore")

    opening = re.search(
        r'<div[^>]*class=["\'][^"\']*\bjournal-grid\b[^"\']*["\'][^>]*id=["\']paperGrid["\'][^>]*>',
        text, re.I | re.S
    )
    if not opening:
        raise RuntimeError('Could not locate <div class="journal-grid" id="paperGrid">')

    start = opening.end()
    pos = start
    depth = 1
    tag_re = re.compile(r"</?div\b[^>]*>", re.I)
    while True:
        m = tag_re.search(text, pos)
        if not m:
            raise RuntimeError("Could not locate closing </div> for paperGrid")
        tag = m.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                end = m.start()
                break
        else:
            depth += 1
        pos = m.end()

    inner = text[start:end]

    existing = set(re.findall(
        r'href=["\'](?:https://nutreconciencia\.com)?/articulos/([^/"\']+)/["\']',
        inner, re.I
    ))

    candidates = []
    for meta in sorted(ART.glob("*/metadata.json")):
        slug = meta.parent.name
        if slug in existing:
            continue
        data = json.loads(meta.read_text(encoding="utf-8"))
        title = clean(data.get("title"))
        year = clean(data.get("year"))
        journal = clean(data.get("journal")) or "Publicación científica"
        if not title or not year:
            raise RuntimeError(f"{slug}: metadata.json missing title or year")
        candidates.append((slug, title, year, journal))

    if not candidates:
        print("="*72)
        print("STEP 9B — RESEARCH INDEX")
        print("="*72)
        print("No new DOI-created cards to insert.")
        return

    def year_num(y):
        m = re.search(r"\b(20\d{2})\b", y)
        return int(m.group(1)) if m else 0

    candidates.sort(key=lambda x: (-year_num(x[2]), x[1].lower()))

    cards = []
    for slug, title, year, journal in candidates:
        cards.append(
            '<article class="paper-cover" data-year="' + escape(year) +
            '" data-title="' + escape(title.lower(), quote=True) + '">' +
            '<a href="/articulos/' + escape(slug) + '/">' +
            '<div class="paper-year">' + escape(year) + '</div>' +
            '<h3>' + escape(title) + '</h3>' +
            '<div class="paper-journal">' + escape(journal) + '</div>' +
            '</a></article>\n'
        )

    updated = text[:start] + "\n" + "".join(cards) + inner + text[end:]
    for slug, title, year, journal in candidates:
        assert f'href="/articulos/{slug}/"' in updated
        assert f'data-year="{year}"' in updated

    INDEX.write_text(updated, encoding="utf-8")

    print("="*72)
    print("STEP 9B — RESEARCH INDEX")
    print("="*72)
    print(f"New DOI-created cards inserted: {len(candidates)}")
    for slug, title, year, journal in candidates:
        print(f" - {year} | {title} | {journal}")
    print("Existing cards preserved.")
    print("#paperGrid structure preserved.")
    print("No sitemap, article pages, .htaccess or schema changes.")

if __name__ == "__main__":
    main()
