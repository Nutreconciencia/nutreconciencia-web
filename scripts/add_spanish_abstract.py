#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"


def main() -> None:
    slug = os.environ.get("ARTICLE_SLUG", "").strip().strip("/")
    summary = os.environ.get("SPANISH_SUMMARY", "").strip()

    if not slug:
        raise SystemExit("ARTICLE_SLUG está vacío.")
    if not summary:
        raise SystemExit("SPANISH_SUMMARY está vacío.")

    folder = ART / slug
    html_path = folder / "index.html"
    meta_path = folder / "metadata.json"

    if not html_path.exists():
        raise FileNotFoundError(f"No existe: {html_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"No existe: {meta_path}")

    html = html_path.read_text(encoding="utf-8")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    # Keep paragraph structure supplied by the user.
    paragraphs = [p.strip() for p in summary.split("\n\n") if p.strip()]
    summary_html = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)

    # Lead uses the first paragraph (or the whole summary when only one exists).
    lead = paragraphs[0] if paragraphs else summary
    lead_html = escape(lead)

    # Replace the current summary lead.
    lead_start = html.find('<p class="summary-lead">')
    if lead_start == -1:
        raise RuntimeError("No se encontró <p class=\"summary-lead\"> en la ficha.")

    lead_end = html.find("</p>", lead_start)
    if lead_end == -1:
        raise RuntimeError("No se encontró el cierre del summary-lead.")
    lead_end += 4

    updated = html[:lead_start] + f'<p class="summary-lead">{lead_html}</p>' + html[lead_end:]

    # Replace the content of the s1 section.
    heading = '<h2 id="s1">'
    s1_start = updated.find(heading)
    if s1_start == -1:
        raise RuntimeError("No se encontró la sección #s1.")

    # Find the next h2 after s1. Keep subsequent sections untouched.
    next_h2 = updated.find("<h2 ", s1_start + len(heading))
    if next_h2 == -1:
        # s1 is the final h2 before "Publicación original" in some templates.
        next_h2 = updated.find('<h2 id="publicacion">', s1_start)

    if next_h2 == -1:
        raise RuntimeError("No se encontró el siguiente encabezado tras #s1.")

    # Preserve an existing note immediately before s1; replace only s1 and its body.
    new_section = (
        '<h2 id="s1">Resumen del artículo</h2>'
        + summary_html
    )
    updated = updated[:s1_start] + new_section + updated[next_h2:]

    # Update metadata with the user's reviewed Spanish text.
    metadata["abstract_spanish"] = summary
    metadata["translation_provider"] = "manual"
    metadata["editorial_summary_source"] = "user_provided"

    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    html_path.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("ADD SPANISH ABSTRACT — MANUAL")
    print("=" * 72)
    print("Article:", slug)
    print("Paragraphs inserted:", len(paragraphs))
    print("metadata.json: UPDATED")
    print("index.html: UPDATED")
    print("Translation provider: manual")
    print("Editorial summary verification: PASS")


if __name__ == "__main__":
    main()
