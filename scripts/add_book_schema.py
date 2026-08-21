#!/usr/bin/env python3
"""
STEP 7 — Add Book + WebPage JSON-LD to /libro/index.html.

Only uses information explicitly present on the page:
- Book title: Comer mentiras.
- Author: Miguel López Moreno, linked to #person.
- Publisher: Espasa.
- Publication year: 2026.
- Cover image: /assets/comer-mentiras.jpg
- Official publisher/book page: PlanetadeLibros URL already present on page.
- Canonical URL: /libro/

Does not invent ISBN, page count, price, rating, availability, or format.
Idempotent: replaces its own generated block if it already exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "libro" / "index.html"

SCHEMA_ID = "nutreconciencia-book-schema"

GRAPH = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "WebPage",
            "@id": "https://nutreconciencia.com/libro/#webpage",
            "url": "https://nutreconciencia.com/libro/",
            "name": "Comer mentiras | Miguel López Moreno",
            "mainEntity": {
                "@id": "https://nutreconciencia.com/libro/#book"
            }
        },
        {
            "@type": "Book",
            "@id": "https://nutreconciencia.com/libro/#book",
            "name": "Comer mentiras",
            "url": "https://nutreconciencia.com/libro/",
            "image": "https://nutreconciencia.com/assets/comer-mentiras.jpg",
            "description": "Cómo evitar engaños entendiendo la ciencia de la nutrición.",
            "author": {
                "@type": "Person",
                "@id": "https://nutreconciencia.com/#person",
                "name": "Miguel López Moreno"
            },
            "publisher": {
                "@type": "Organization",
                "name": "Espasa"
            },
            "datePublished": "2026",
            "sameAs": [
                "https://www.planetadelibros.com/libro-comer-mentiras/454435"
            ]
        }
    ]
}


def main() -> None:
    if not PAGE.exists():
        raise FileNotFoundError("No existe libro/index.html")

    text = PAGE.read_text(encoding="utf-8", errors="ignore")

    block_re = re.compile(
        r'\s*<script type="application/ld\+json" id="'
        + re.escape(SCHEMA_ID)
        + r'">.*?</script>\s*',
        flags=re.I | re.S,
    )

    block = (
        f'<script type="application/ld+json" id="{SCHEMA_ID}">\n'
        + json.dumps(GRAPH, ensure_ascii=False, indent=2)
        + "\n</script>\n"
    )

    if block_re.search(text):
        updated = block_re.sub("\n" + block, text, count=1)
        changed = updated != text
    else:
        m = re.search(r"</head>", text, flags=re.I)
        if not m:
            raise RuntimeError("No se encontró </head> en libro/index.html")
        updated = text[:m.start()] + block + text[m.start():]
        changed = True

    PAGE.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("STEP 7 — BOOK + WEBPAGE SCHEMA")
    print("=" * 72)
    print("Page: libro/index.html")
    print("Book @id: https://nutreconciencia.com/libro/#book")
    print("Author @id: https://nutreconciencia.com/#person")
    print("Publisher: Espasa")
    print("Date published: 2026")
    print(f"Page modified: {changed}")
    print("No ISBN, price, rating, availability, page count or book format were guessed.")


if __name__ == "__main__":
    main()
