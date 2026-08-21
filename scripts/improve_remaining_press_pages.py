#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "prensa"
AUDIT = ROOT / "press_pages_audit.csv"

TARGET_SLUGS = [
    "20minutos-piramide",
    "actual-fruveg",
    "agencia-sinc-nutricion",
    "eldiario-greenwashing",
    "instituto-nutrigenomica",
    "la-vanguardia-seeds",
    "la-voz-galicia-meat",
    "la-voz-galicia-omniveg",
    "pcrm-omniveg",
    "plantrician-omniveg",
    "vozpopuli-omniveg",
]

PUBLISHERS = {
    "20minutos-piramide": "20minutos",
    "actual-fruveg": "Actual FruVeg",
    "agencia-sinc-nutricion": "Agencia SINC",
    "eldiario-greenwashing": "elDiario.es",
    "instituto-nutrigenomica": "Instituto Nutrigenómica",
    "la-vanguardia-seeds": "La Vanguardia",
    "la-voz-galicia-meat": "La Voz de Galicia",
    "la-voz-galicia-omniveg": "La Voz de Galicia",
    "pcrm-omniveg": "Physicians Committee for Responsible Medicine",
    "plantrician-omniveg": "Plantrician Project",
    "vozpopuli-omniveg": "Vozpópuli",
}

# Multiple generic wordings that have appeared in different press templates.
GENERIC_LEADS = [
    "Aparición pública vinculada a investigación, divulgación o análisis de nutrición y salud.",
]

GENERIC_PUBLICATIONS = [
    "Esta ficha recoge el titular, el medio y la fecha y enlaza directamente a la fuente original.",
]

GENERIC_REVIEWS = [
    "Una ficha de prensa que recoge la aparición de Miguel López Moreno, resume brevemente su enfoque y enlaza a la publicación original.",
    "Una ficha de prensa que recoge la aparición de Miguel López Moreno y enlaza a la publicación original.",
    "Esta ficha recoge la aparición de Miguel López Moreno y enlaza a la publicación original.",
]

def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()

def load_rows():
    with AUDIT.open("r", encoding="utf-8", newline="") as f:
        data = {r["slug"]: r for r in csv.DictReader(f)}
    missing = [s for s in TARGET_SLUGS if s not in data]
    if missing:
        raise RuntimeError("Missing audit rows: " + ", ".join(missing))
    return data

def replace_first_if_present(text: str, alternatives: list[str], new: str) -> tuple[str, bool]:
    for old in alternatives:
        if old in text:
            return text.replace(old, new, 1), True
    return text, False

def main():
    rows = load_rows()
    modified = 0
    skipped_parts = []

    for slug in TARGET_SLUGS:
        row = rows[slug]
        page = PRESS / slug / "index.html"
        if not page.exists():
            raise FileNotFoundError(page)

        title = clean(row.get("title"))
        publisher = PUBLISHERS[slug]
        if not title:
            raise RuntimeError(f"{slug}: empty title in audit CSV")

        lead = (
            f"La publicación de {publisher} recoge la aparición de Miguel López Moreno "
            f"y aborda el tema reflejado en el titular: “{title}”."
        )
        publication = (
            f"El artículo publicado por {publisher} conserva la referencia original "
            f"de la noticia y permite consultar directamente la pieza completa en el medio."
        )
        review = (
            f"Esta ficha de prensa reúne la aparición publicada por {publisher} y la "
            f"mantiene vinculada a su fuente original, sin sustituir ni reinterpretar "
            f"el contenido de la noticia."
        )

        text = page.read_text(encoding="utf-8", errors="ignore")
        updated = text
        found_any = False

        updated, found = replace_first_if_present(updated, GENERIC_LEADS, lead)
        found_any = found_any or found
        if not found:
            skipped_parts.append(f"{slug}: lead already non-generic or different template")

        updated, found = replace_first_if_present(updated, GENERIC_PUBLICATIONS, publication)
        found_any = found_any or found
        if not found:
            skipped_parts.append(f"{slug}: publication text already non-generic or different template")

        updated, found = replace_first_if_present(updated, GENERIC_REVIEWS, review)
        found_any = found_any or found
        if not found:
            skipped_parts.append(f"{slug}: review text already non-generic or different template")

        if updated != text:
            page.write_text(updated, encoding="utf-8")
            modified += 1

    print("=" * 72)
    print("STEP 8C V2 — COMPLETE REMAINING PRESS PAGES")
    print("=" * 72)
    print(f"Target pages: {len(TARGET_SLUGS)}")
    print(f"Pages modified: {modified}")
    print("El Mundo OMNIVEG was not modified by this workflow.")
    print("No canonical, OG, Twitter or schema changes were made.")

    if skipped_parts:
        print("\nNOTES:")
        for item in skipped_parts:
            print("-", item)

if __name__ == "__main__":
    main()
