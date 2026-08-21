#!/usr/bin/env python3
"""
STEP 8D — Normalize all press pages into one editorial structure.

Runs against every prensa/*/index.html and uses the already existing page
content as the factual source. It does NOT fetch external news websites.

For each page it:
- keeps the existing H1/title;
- keeps the existing outlet/date when present;
- extracts a substantive existing paragraph from the page body;
- rewrites the three template areas into:
    1) a specific lead based on the existing page content;
    2) "La publicación" section with a concise source-grounded description;
    3) "BREVE RESEÑA" with a neutral contextual note;
- does not invent results, dates or details not already present in the page.

It does not modify canonical, OG/Twitter, JSON-LD, sitemap.xml or .htaccess.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "prensa"

GENERIC_PATTERNS = [
    "Aparición pública vinculada a investigación, divulgación o análisis de nutrición y salud.",
    "Esta ficha recoge el titular, el medio y la fecha y enlaza directamente a la fuente original.",
    "Una ficha de prensa que recoge la aparición de Miguel López Moreno, resume brevemente su enfoque y enlaza a la publicación original.",
    "Una ficha de prensa que recoge la aparición de Miguel López Moreno y enlaza a la publicación original.",
    "Esta ficha recoge la aparición de Miguel López Moreno y enlaza a la publicación original.",
]

def clean(v: str) -> str:
    v = html.unescape(v or "")
    return re.sub(r"\s+", " ", v).strip()

def extract_h1(text: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S)
    return clean(re.sub(r"<[^>]+>", " ", m.group(1))) if m else ""

def extract_meta_description(text: str) -> str:
    m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
        text, re.I | re.S
    )
    return clean(m.group(1)) if m else ""

def extract_paragraphs(text: str) -> list[str]:
    # Prefer the main article region where present.
    main_match = re.search(
        r"<main\b[^>]*>(.*?)</main>",
        text, re.I | re.S
    )
    region = main_match.group(1) if main_match else text

    paragraphs = []
    for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", region, re.I | re.S):
        value = clean(re.sub(r"<[^>]+>", " ", m.group(1)))
        if not value:
            continue
        if any(g.lower() in value.lower() for g in GENERIC_PATTERNS):
            continue
        if len(value) < 45:
            continue
        paragraphs.append(value)

    return paragraphs

def extract_outlet_and_date(text: str) -> tuple[str, str]:
    # Common pattern: outlet and date in adjacent text.
    # We do not create or alter this field if we cannot identify it.
    year = re.search(r"\b(20\d{2})\b", text)
    date = year.group(1) if year else ""

    outlet_candidates = [
        "EL MUNDO", "The New York Times", "The Times", "The Washington Post",
        "20minutos", "La Vanguardia", "La Voz de Galicia", "Vozpópuli",
        "Agencia SINC", "elDiario.es", "Plantrician Project",
        "Physicians Committee for Responsible Medicine", "Actual FruVeg",
        "Fit Generation", "Instituto Nutrigenómica"
    ]

    low = text.lower()
    outlet = next((x for x in outlet_candidates if x.lower() in low), "")
    return outlet, date

def replace_generic(text: str, old: str, new: str) -> tuple[str, bool]:
    if old not in text:
        return text, False
    return text.replace(old, new, 1), True

def main():
    pages = sorted(PRESS.glob("*/index.html"))
    if not pages:
        raise RuntimeError("No press pages found.")

    modified = 0
    notes = []

    for page in pages:
        text = page.read_text(encoding="utf-8", errors="ignore")

        title = extract_h1(text)
        description = extract_meta_description(text)
        paragraphs = extract_paragraphs(text)
        outlet, year = extract_outlet_and_date(text)

        # Use the actual page's description/paragraph as factual source.
        factual = description if len(description) >= 60 else (
            paragraphs[0] if paragraphs else ""
        )

        if not title:
            notes.append(f"{page.parent.name}: no H1/title found")
            continue

        if not factual:
            factual = (
                f"La publicación aborda el tema reflejado en el titular: "
                f"“{title}”."
            )

        lead = factual
        publication = (
            f"La pieza recoge información relacionada con «{title}»"
            + (f" y fue publicada por {outlet}." if outlet else ".")
        )

        if paragraphs:
            second = paragraphs[1] if len(paragraphs) > 1 else paragraphs[0]
            review = second
        else:
            review = (
                f"La noticia permite contextualizar la presencia de Miguel López Moreno "
                f"en medios a partir del contenido de esta publicación."
            )

        updated = text
        changed_here = False

        # Replace known generic fragments wherever they occur.
        for old in GENERIC_PATTERNS:
            if old in updated:
                # Choose semantic replacement according to the old wording.
                if old == GENERIC_PATTERNS[0]:
                    new = lead
                elif old == GENERIC_PATTERNS[1]:
                    new = publication
                else:
                    new = review
                updated = updated.replace(old, new, 1)
                changed_here = True

        # If the page already has the desired non-generic copy, don't overwrite it.
        # If none of the known generic fragments are present, leave page intact.
        if changed_here:
            page.write_text(updated, encoding="utf-8")
            modified += 1

    print("=" * 72)
    print("STEP 8D — NORMALIZE PRESS PAGE COPY")
    print("=" * 72)
    print(f"Press pages found: {len(pages)}")
    print(f"Pages modified: {modified}")
    print(f"Pages already non-generic / not changed: {len(pages) - modified}")
    print("Source basis: existing page title/meta description/body only.")
    print("No external news pages were fetched.")
    print("No canonical, OG/Twitter, JSON-LD, sitemap or .htaccess changes.")

    if notes:
        print("\nNOTES:")
        for note in notes:
            print("-", note)

if __name__ == "__main__":
    main()
