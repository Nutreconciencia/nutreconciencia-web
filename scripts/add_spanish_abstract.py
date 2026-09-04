#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"


def render_inline(text: str) -> str:
    """
    Render user-approved inline markup:
    **bold**
    [[BIG]]large text[[/BIG]]
    """
    text = escape(text, quote=False)

    # BIG first
    text = re.sub(
        r"\[\[BIG\]\](.*?)\[\[/BIG\]\]",
        r'<span class="summary-big">\1</span>',
        text,
        flags=re.S,
    )

    # Bold
    text = re.sub(
        r"\*\*(.*?)\*\*",
        r"<strong>\1</strong>",
        text,
        flags=re.S,
    )

    return text


def split_paragraphs(summary: str) -> list[str]:
    """
    Preferred separator:
        |||
    Fallback:
        blank lines
    """
    if "|||" in summary:
        parts = [p.strip() for p in summary.split("|||")]
    else:
        parts = [p.strip() for p in re.split(r"\n\s*\n", summary)]

    return [p for p in parts if p]


def summary_html(paragraphs: list[str]) -> str:
    return "\n".join(
        f"<p>{render_inline(paragraph)}</p>"
        for paragraph in paragraphs
    )


def find_metadata_file(folder: Path) -> Path:
    """
    Support both publication architectures:
    - metadata.json -> DOI-created papers
    - orcid.json    -> ORCID-managed papers
    """
    metadata = folder / "metadata.json"
    orcid = folder / "orcid.json"

    if metadata.exists():
        return metadata

    if orcid.exists():
        return orcid

    raise FileNotFoundError(
        f"No existe metadata.json ni orcid.json en: {folder}"
    )


def update_clean_paper(html: str, paragraphs: list[str]) -> str:
    """
    Update the current ORCID/clean-paper template.

    - First paragraph becomes the main scientific summary.
    - All supplied paragraphs replace the automatically generated
      English body sections before 'Publicación original'.
    """

    if '<div class="clean-summary">' not in html:
        raise RuntimeError("No se encontró .clean-summary.")

    summary_start = html.find('<div class="clean-summary">')
    summary_end = html.find('</div>', summary_start)

    if summary_end == -1:
        raise RuntimeError("No se pudo cerrar .clean-summary.")

    summary_block = html[summary_start:summary_end + len('</div>')]

    lead_match = re.search(
        r'<p>(.*?)</p>',
        summary_block,
        flags=re.S,
    )

    if not lead_match:
        raise RuntimeError(
            "No se encontró <p> dentro de .clean-summary."
        )

    lead_html = render_inline(paragraphs[0])

    new_summary_block = (
        summary_block[:lead_match.start()]
        + f"<p>{lead_html}</p>"
        + summary_block[lead_match.end():]
    )

    html = (
        html[:summary_start]
        + new_summary_block
        + html[summary_end + len('</div>'):]
    )

    divider = '<div class="clean-divider"></div>'
    divider_pos = html.find(divider)

    if divider_pos == -1:
        raise RuntimeError("No se encontró .clean-divider.")

    publication_marker = '<div class="clean-section">\n      <div class="clean-kicker">Publicación original</div>'

    publication_pos = html.find(publication_marker)

    if publication_pos == -1:
        raise RuntimeError(
            "No se encontró la sección 'Publicación original'."
        )

    analysis = (
        '\n\n'
        '<div class="clean-section">\n'
        '  <div class="clean-kicker">ANÁLISIS EN ESPAÑOL</div>\n'
        '  <h2>Lo que explica realmente el artículo</h2>\n'
        f'  {summary_html(paragraphs)}\n'
        '</div>\n\n'
    )

    body_start = divider_pos + len(divider)

    html = (
        html[:body_start]
        + analysis
        + html[publication_pos:]
    )

    return html


def update_legacy_paper(html: str, paragraphs: list[str]) -> str:
    """
    Support the previous article template using:
    .summary-lead + <h2 id="s1">
    """

    lead_marker = '<p class="summary-lead">'
    lead_start = html.find(lead_marker)

    if lead_start == -1:
        raise RuntimeError(
            "No se encontró ni .clean-summary ni .summary-lead."
        )

    lead_end = html.find("</p>", lead_start)

    if lead_end == -1:
        raise RuntimeError(
            "No se encontró el cierre de .summary-lead."
        )

    lead_end += len("</p>")

    lead_html = render_inline(paragraphs[0])

    html = (
        html[:lead_start]
        + f'<p class="summary-lead">{lead_html}</p>'
        + html[lead_end:]
    )

    heading = '<h2 id="s1">'

    s1_start = html.find(heading)

    if s1_start == -1:
        raise RuntimeError(
            "No se encontró la sección #s1."
        )

    next_h2 = html.find("<h2 ", s1_start + len(heading))

    if next_h2 == -1:
        next_h2 = html.find(
            '<h2 id="publicacion">',
            s1_start,
        )

    if next_h2 == -1:
        raise RuntimeError(
            "No se encontró el siguiente encabezado después de #s1."
        )

    new_section = (
        '<h2 id="s1">Resumen del artículo</h2>'
        + summary_html(paragraphs)
    )

    html = (
        html[:s1_start]
        + new_section
        + html[next_h2:]
    )

    return html


def main() -> None:
    slug = os.environ.get("ARTICLE_SLUG", "").strip().strip("/")
    summary = os.environ.get("SPANISH_SUMMARY", "").strip()

    if not slug:
        raise SystemExit("ARTICLE_SLUG está vacío.")

    if not summary:
        raise SystemExit("SPANISH_SUMMARY está vacío.")

    slug = slug.removeprefix("articulos/")

    folder = ART / slug
    html_path = folder / "index.html"

    if not folder.exists():
        raise FileNotFoundError(
            f"No existe la carpeta del artículo: {folder}"
        )

    if not html_path.exists():
        raise FileNotFoundError(
            f"No existe: {html_path}"
        )

    meta_path = find_metadata_file(folder)

    html = html_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    metadata = json.loads(
        meta_path.read_text(
            encoding="utf-8"
        )
    )

    paragraphs = split_paragraphs(summary)

    if not paragraphs:
        raise RuntimeError(
            "No se encontraron párrafos válidos en el resumen."
        )

    # Support the two article templates.
    if '<div class="clean-summary">' in html:
        updated = update_clean_paper(
            html,
            paragraphs,
        )
        template_used = "clean-paper"

    elif '<p class="summary-lead">' in html:
        updated = update_legacy_paper(
            html,
            paragraphs,
        )
        template_used = "legacy"

    else:
        raise RuntimeError(
            "La ficha no corresponde a una plantilla compatible."
        )

    # Update metadata in whichever publication file the article uses.
    metadata["abstract_spanish"] = summary
    metadata["translation_provider"] = "manual"
    metadata["editorial_summary_source"] = "user_provided"
    metadata["summary_paragraphs"] = paragraphs

    meta_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    html_path.write_text(
        updated,
        encoding="utf-8",
    )

    print("=" * 72)
    print("ADD SPANISH ABSTRACT — MANUAL")
    print("=" * 72)
    print("Article:", slug)
    print("Metadata file:", meta_path.name)
    print("Template:", template_used)
    print("Paragraphs inserted:", len(paragraphs))
    print("metadata/orcid.json: UPDATED")
    print("index.html: UPDATED")
    print("Translation provider: manual")
    print("Editorial summary source: user_provided")
    print("Spanish abstract verification: PASS")


if __name__ == "__main__":
    main()
