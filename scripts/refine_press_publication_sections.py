#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "prensa"

# Specific "La publicación" copy for all 19 existing press pages.
PUBLICATION = {
    "20minutos-piramide":
        "20minutos analiza la nueva pirámide nutricional de EE. UU. y recoge el debate sobre los criterios que deben guiar las recomendaciones nutricionales.",
    "actual-fruveg":
        "Actual FruVeg aborda la sustitución de proteína animal por proteína vegetal y sus implicaciones dentro de la alimentación.",
    "agencia-sinc-nutricion":
        "Agencia SINC aborda por qué distintos estudios de nutrición pueden llegar a conclusiones diferentes y la importancia de interpretar la evidencia en su contexto.",
    "carne-roja":
        "Esta publicación aborda la evidencia sobre carne roja y salud y destaca la importancia de considerar con qué alimento se compara su consumo.",
    "el-mundo":
        "El Mundo analiza qué podemos concluir realmente de la evidencia disponible sobre carne roja y salud y pone el foco en la importancia del contexto.",
    "el-mundo-omniveg":
        "El Mundo recoge los resultados del estudio OMNIVEG y aborda los efectos de sustituir fuentes de proteína animal por fuentes de proteína vegetal dentro de un patrón de dieta mediterránea.",
    "eldiario-greenwashing":
        "elDiario.es aborda la responsabilidad climática y ética de los supermercados frente al greenwashing en el sector de la alimentación.",
    "instituto-nutrigenomica":
        "El Instituto de Nutrigenómica presenta avances relacionados con microbiota, salud planetaria y envejecimiento dentro de la investigación en nutrición.",
    "la-vanguardia-seeds":
        "La Vanguardia recoge la perspectiva de Miguel López Moreno sobre las afirmaciones que presentan los aceites de semillas como un problema grave de salud pública.",
    "la-voz-galicia-meat":
        "La Voz de Galicia recoge la perspectiva de Miguel López Moreno sobre la relación entre el consumo de carne y el riesgo cardiovascular.",
    "la-voz-galicia-omniveg":
        "La Voz de Galicia presenta los resultados del estudio OMNIVEG y destaca los cambios observados al sustituir proteína animal por proteína vegetal dentro de la dieta mediterránea.",
    "pcrm-omniveg":
        "Physicians Committee for Responsible Medicine presenta los principales resultados del estudio OMNIVEG y la comparación entre una dieta mediterránea vegana y una dieta mediterránea convencional.",
    "perfil-fit-generation":
        "Fit Generation presenta la trayectoria profesional de Miguel López Moreno y su actividad en investigación, docencia y divulgación en nutrición.",
    "plantrician-omniveg":
        "Plantrician Project ofrece una lectura divulgativa del estudio OMNIVEG y de la comparación entre una dieta mediterránea tradicional y una dieta mediterránea vegana.",
    "podcast-dieta-mediterranea":
        "La conversación aborda la dieta mediterránea, las dietas basadas en plantas y la interpretación de la evidencia nutricional.",
    "the-new-york-times":
        "The New York Times aborda qué dice realmente la investigación sobre carne roja y salud cardiovascular y cómo interpretar la evidencia disponible.",
    "the-times":
        "The Times analiza la controversia científica alrededor de la carne roja y la salud cardiovascular y el contexto en el que se ha generado la evidencia.",
    "vozpopuli-omniveg":
        "Vozpópuli aborda los posibles beneficios y algunos inconvenientes de la dieta mediterránea vegana.",
    "washington-post":
        "The Washington Post aborda si la carne roja es perjudicial para la salud y destaca los límites de la evidencia disponible para obtener una respuesta definitiva.",
}

OLD_GENERIC = "El artículo publicado por El Mundo conserva la referencia original de la noticia y permite consultar directamente la pieza completa en el medio."

def replace_after_heading(text: str, heading_variants: list[str], new_text: str) -> tuple[str, bool]:
    # Match heading and the immediately following paragraph, regardless of
    # whether the heading is strong, h2, h3 or wrapped in another element.
    pattern = re.compile(
        r'((?:<[^>]+>)*\s*(?:' + "|".join(heading_variants) + r')\s*(?:</[^>]+>)*\s*)'
        r'(<p\b[^>]*>).*?(</p>)',
        re.I | re.S,
    )
    m = pattern.search(text)
    if not m:
        return text, False
    replacement = m.group(1) + m.group(2) + new_text + m.group(3)
    return text[:m.start()] + replacement + text[m.end():], True

def main():
    pages = sorted(PRESS.glob("*/index.html"))
    modified = 0
    notes = []

    for page in pages:
        slug = page.parent.name
        if slug not in PUBLICATION:
            continue

        text = page.read_text(encoding="utf-8", errors="ignore")
        updated = text
        new_text = PUBLICATION[slug]

        # First try the exact generic sentence known from the pages.
        if OLD_GENERIC in updated:
            updated = updated.replace(OLD_GENERIC, new_text, 1)
            changed = True
        else:
            updated, changed = replace_after_heading(
                updated,
                [r"La publicación", r"La\s+publicación"],
                new_text
            )

        if changed:
            page.write_text(updated, encoding="utf-8")
            modified += 1
        else:
            notes.append(f"{slug}: La publicación section not matched")

    print("=" * 72)
    print("STEP 8E — PRESS PUBLICATION SECTIONS")
    print("=" * 72)
    print(f"Press pages scanned: {len(pages)}")
    print(f"Pages modified: {modified}")
    print(f"Pages requiring review: {len(notes)}")
    for note in notes:
        print("-", note)

if __name__ == "__main__":
    main()
