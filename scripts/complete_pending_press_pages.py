#!/usr/bin/env python3
"""
STEP 8B — Complete the 12 pending press pages.

Source of truth:
- press_pages_audit.csv

Only pages without a canonical in the audit are modified.

Adds:
- canonical
- og:title
- og:description
- og:type
- og:url
- og:image
- twitter:card
- twitter:title
- twitter:description
- twitter:image
- NewsArticle JSON-LD

No dates are invented. No page is treated as a press item unless it is
already present in prensa/.
"""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "prensa"
AUDIT = ROOT / "press_pages_audit.csv"
IMAGE = "https://nutreconciencia.com/assets/miguel-lopez-moreno.jpg"
PERSON = "https://nutreconciencia.com/#person"

PUBLISHERS = {
    "20minutos-piramide": "20minutos",
    "actual-fruveg": "Actual FruVeg",
    "agencia-sinc-nutricion": "Agencia SINC",
    "el-mundo-omniveg": "El Mundo",
    "eldiario-greenwashing": "elDiario.es",
    "instituto-nutrigenomica": "Instituto Nutrigenómica",
    "la-vanguardia-seeds": "La Vanguardia",
    "la-voz-galicia-meat": "La Voz de Galicia",
    "la-voz-galicia-omniveg": "La Voz de Galicia",
    "pcrm-omniveg": "Physicians Committee for Responsible Medicine",
    "plantrician-omniveg": "Plantrician Project",
    "vozpopuli-omniveg": "Vozpópuli",
}


def clean(v: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(v or "")).strip()


def meta_tag(prop: str, value: str) -> str:
    return f'<meta property="{prop}" content="{html.escape(value, quote=True)}">'


def name_meta(name: str, value: str) -> str:
    return f'<meta name="{name}" content="{html.escape(value, quote=True)}">'


def replace_or_add_meta(text: str, kind: str, key: str, value: str) -> str:
    if kind == "property":
        pat = re.compile(
            rf'<meta\b[^>]*property=["\']{re.escape(key)}["\'][^>]*>',
            re.I | re.S,
        )
        tag = meta_tag(key, value)
    else:
        pat = re.compile(
            rf'<meta\b[^>]*name=["\']{re.escape(key)}["\'][^>]*>',
            re.I | re.S,
        )
        tag = name_meta(key, value)

    if pat.search(text):
        return pat.sub(tag, text, count=1)

    head = re.search(r"</head>", text, re.I)
    if not head:
        raise RuntimeError("No </head> found")
    return text[:head.start()] + tag + "\n" + text[head.start():]


def remove_generated_schema(text: str) -> str:
    return re.sub(
        r'\s*<script type="application/ld\+json" id="nutreconciencia-press-schema">.*?</script>\s*',
        "\n",
        text,
        flags=re.I | re.S,
    )


def build_schema(slug: str, title: str, original_url: str, publisher: str) -> dict:
    canonical = f"https://nutreconciencia.com/prensa/{slug}/"

    article = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "@id": canonical.rstrip("/") + "/#newsarticle",
        "url": canonical,
        "headline": title,
        "image": [IMAGE],
        "author": {
            "@type": "Person",
            "@id": PERSON,
            "name": "Miguel López Moreno",
        },
        "publisher": {
            "@type": "Organization",
            "name": publisher,
        },
        "sameAs": [original_url],
    }

    return article


def inject_schema(text: str, schema: dict) -> str:
    text = remove_generated_schema(text)

    block = (
        '<script type="application/ld+json" id="nutreconciencia-press-schema">\n'
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + "\n</script>\n"
    )

    head = re.search(r"</head>", text, re.I)
    if not head:
        raise RuntimeError("No </head> found")
    return text[:head.start()] + block + text[head.start():]


def main():
    if not AUDIT.exists():
        raise FileNotFoundError("press_pages_audit.csv not found")

    with AUDIT.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    pending = [r for r in rows if not clean(r.get("canonical", ""))]

    if len(pending) != 12:
        raise RuntimeError(
            f"Expected 12 pending press pages; found {len(pending)}"
        )

    modified = 0

    for row in pending:
        slug = clean(row.get("slug"))
        title = clean(row.get("title"))
        original_url = clean(row.get("original_url_candidate"))

        if not slug or not title or not original_url:
            raise RuntimeError(f"Incomplete press row: {row}")

        page = PRESS / slug / "index.html"
        if not page.exists():
            raise FileNotFoundError(page)

        canonical = f"https://nutreconciencia.com/prensa/{slug}/"
        publisher = PUBLISHERS.get(slug, clean(urlparse(original_url).netloc))

        text = page.read_text(encoding="utf-8", errors="ignore")

        og_title = f"{title} | Miguel López Moreno"
        og_description = f"{title} — aparición de Miguel López Moreno en {publisher}."

        updated = text

        # Canonical
        canonical_re = re.compile(
            r'<link\b[^>]*rel=["\']canonical["\'][^>]*>',
            re.I | re.S,
        )
        canonical_tag = f'<link rel="canonical" href="{canonical}">'
        if canonical_re.search(updated):
            updated = canonical_re.sub(canonical_tag, updated, count=1)
        else:
            head = re.search(r"</head>", updated, re.I)
            if not head:
                raise RuntimeError(f"No </head> in {page}")
            updated = updated[:head.start()] + canonical_tag + "\n" + updated[head.start():]

        updated = replace_or_add_meta(updated, "property", "og:title", og_title)
        updated = replace_or_add_meta(updated, "property", "og:description", og_description)
        updated = replace_or_add_meta(updated, "property", "og:type", "article")
        updated = replace_or_add_meta(updated, "property", "og:url", canonical)
        updated = replace_or_add_meta(updated, "property", "og:image", IMAGE)

        updated = replace_or_add_meta(updated, "name", "twitter:card", "summary_large_image")
        updated = replace_or_add_meta(updated, "name", "twitter:title", og_title)
        updated = replace_or_add_meta(updated, "name", "twitter:description", og_description)
        updated = replace_or_add_meta(updated, "name", "twitter:image", IMAGE)

        updated = inject_schema(
            updated,
            build_schema(slug, title, original_url, publisher),
        )

        page.write_text(updated, encoding="utf-8")
        modified += 1

    print("=" * 72)
    print("STEP 8B — COMPLETE PENDING PRESS PAGES")
    print("=" * 72)
    print(f"Pending pages found: {len(pending)}")
    print(f"Pages modified: {modified}")
    print("Canonical + Open Graph + Twitter + NewsArticle added.")
    print("No dates were invented.")
    print("Existing press pages with canonical were not modified.")


if __name__ == "__main__":
    main()
