#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "prensa"
AUDIT = ROOT / "press_pages_audit.csv"

PUBLISHERS = {
    '20minutos-piramide': '20minutos',
    'actual-fruveg': 'Actual FruVeg',
    'agencia-sinc-nutricion': 'Agencia SINC',
    'carne-roja': '—',
    'el-mundo': 'el medio',
    'el-mundo-omniveg': 'El Mundo',
    'eldiario-greenwashing': 'elDiario.es',
    'instituto-nutrigenomica': 'Instituto Nutrigenómica',
    'la-vanguardia-seeds': 'La Vanguardia',
    'la-voz-galicia-meat': 'La Voz de Galicia',
    'la-voz-galicia-omniveg': 'La Voz de Galicia',
    'pcrm-omniveg': 'Physicians Committee for Responsible Medicine',
    'perfil-fit-generation': 'Fit Generation',
    'plantrician-omniveg': 'Plantrician Project',
    'podcast-dieta-mediterranea': 'Fit Generation',
    'the-new-york-times': 'The New York Times',
    'the-times': 'The Times',
    'vozpopuli-omniveg': 'Vozpópuli',
    'washington-post': 'The Washington Post',
}

GENERIC_LEAD_VARIANTS = [
    "Aparición pública vinculada a investigación, divulgación o análisis de nutrición y salud.",
]

GENERIC_PUBLICATION_VARIANTS = [
    "Esta ficha recoge el titular, el medio y la fecha y enlaza directamente a la fuente original.",
]

GENERIC_REVIEW_VARIANTS = [
    "Una ficha de prensa que recoge la aparición de Miguel López Moreno, resume brevemente su enfoque y enlaza a la publicación original.",
    "Una ficha de prensa que recoge la aparición de Miguel López Moreno y enlaza a la publicación original.",
    "Esta ficha recoge la aparición de Miguel López Moreno y enlaza a la publicación original.",
]

def clean(v: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(v or "")).strip()

def replace_first(text: str, variants: list[str], new: str) -> tuple[str, bool]:
    for old in variants:
        if old in text:
            return text.replace(old, new, 1), True
    return text, False

def main():
    if not AUDIT.exists():
        raise FileNotFoundError("press_pages_audit.csv not found")

    with AUDIT.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise RuntimeError("press_pages_audit.csv is empty")

    modified = 0
    generic_before = 0
    generic_after = 0
    notes = []

    for row in rows:
        slug = clean(row.get("slug"))
        title = clean(row.get("title"))
        publisher = PUBLISHERS.get(slug, "el medio")

        page = PRESS / slug / "index.html"
        if not page.exists():
            raise FileNotFoundError(page)

        if not title:
            notes.append(f"{slug}: no title in audit; page left unchanged")
            continue

        text = page.read_text(encoding="utf-8", errors="ignore")
        updated = text

        # Specific but deliberately conservative copy: based only on the
        # existing title and identified outlet; no unverified study results
        # or dates are introduced.
        lead = (
            f"La publicación de {publisher} recoge la aparición de Miguel López Moreno "
            f"y aborda el tema reflejado en el titular: “{title}”."
        )

        publication = (
            f"El artículo publicado por {publisher} conserva la referencia original "
            f"de la noticia y permite consultar directamente la pieza completa en el medio."
        )

        review = (
            f"Esta ficha reúne la aparición publicada por {publisher} y la mantiene "
            f"vinculada a su fuente original, para contextualizar la presencia de Miguel "
            f"López Moreno en medios de comunicación."
        )

        found_any = False

        if any(v in updated for v in GENERIC_LEAD_VARIANTS):
            generic_before += 1
        updated, found = replace_first(updated, GENERIC_LEAD_VARIANTS, lead)
        found_any = found_any or found

        updated, found = replace_first(updated, GENERIC_PUBLICATION_VARIANTS, publication)
        found_any = found_any or found

        updated, found = replace_first(updated, GENERIC_REVIEW_VARIANTS, review)
        found_any = found_any or found

        # If the page uses a different pre-existing generic paragraph, do not
        # overwrite it blindly; report it for manual review.
        if found_any:
            modified += 1
        else:
            notes.append(f"{slug}: no known generic template text found")

        page.write_text(updated, encoding="utf-8", errors="ignore")

    print("=" * 72)
    print("STEP 8C — NORMALIZE ALL PRESS PAGE COPY")
    print("=" * 72)
    print(f"Press pages in audit: {len(rows)}")
    print(f"Pages modified: {modified}")
    print(f"Pages with known generic lead before change: {generic_before}")
    print(f"Pages requiring manual review: {len(notes)}")
    print("")
    if notes:
        print("NOTES:")
        for note in notes:
            print("-", note)
    print("")
    print("No canonical, Open Graph, Twitter, schema, sitemap or .htaccess rules were changed.")

if __name__ == "__main__":
    main()
