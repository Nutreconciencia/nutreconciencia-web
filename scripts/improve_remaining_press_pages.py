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
    "20minutos-piramide": '20minutos',
    "actual-fruveg": 'Actual FruVeg',
    "agencia-sinc-nutricion": 'Agencia SINC',
    "eldiario-greenwashing": 'elDiario.es',
    "instituto-nutrigenomica": 'Instituto Nutrigenómica',
    "la-vanguardia-seeds": 'La Vanguardia',
    "la-voz-galicia-meat": 'La Voz de Galicia',
    "la-voz-galicia-omniveg": 'La Voz de Galicia',
    "pcrm-omniveg": 'Physicians Committee for Responsible Medicine',
    "plantrician-omniveg": 'Plantrician Project',
    "vozpopuli-omniveg": 'Vozpópuli',
}

OLD_LEAD = "Aparición pública vinculada a investigación, divulgación o análisis de nutrición y salud."
OLD_PUBLICATION = "Esta ficha recoge el titular, el medio y la fecha y enlaza directamente a la fuente original."
OLD_REVIEW = "Una ficha de prensa que recoge la aparición de Miguel López Moreno, resume brevemente su enfoque y enlaza a la publicación original."

def clean(value: str) -> str:
    return re.sub(r"\\s+", " ", html.unescape(value or "")).strip()

def load_rows():
    with AUDIT.open("r", encoding="utf-8", newline="") as f:
        data = {r["slug"]: r for r in csv.DictReader(f)}
    missing = [s for s in TARGET_SLUGS if s not in data]
    if missing:
        raise RuntimeError("Missing audit rows: " + ", ".join(missing))
    return data

def replace_once(text: str, old: str, new: str, slug: str) -> str:
    if old not in text:
        raise RuntimeError(f"{slug}: expected generic text not found: {old!r}")
    return text.replace(old, new, 1)

def main():
    rows = load_rows()
    modified = 0

    for slug in TARGET_SLUGS:
        row = rows[slug]
        page = PRESS / slug / "index.html"
        if not page.exists():
            raise FileNotFoundError(page)

        title = clean(row.get("title"))
        publisher = PUBLISHERS[slug]

        if not title:
            raise RuntimeError(f"{slug}: empty title in press_pages_audit.csv")

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
        updated = replace_once(updated, OLD_LEAD, lead, slug)
        updated = replace_once(updated, OLD_PUBLICATION, publication, slug)
        updated = replace_once(updated, OLD_REVIEW, review, slug)

        page.write_text(updated, encoding="utf-8")
        modified += 1

    print("=" * 72)
    print("STEP 8C — COMPLETE REMAINING PRESS PAGES")
    print("=" * 72)
    print(f"Target pages: {len(TARGET_SLUGS)}")
    print(f"Pages modified: {modified}")
    print("El Mundo OMNIVEG was not modified by this workflow.")
    print("Canonical, OG, Twitter and NewsArticle schema were not changed.")

if __name__ == "__main__":
    main()
