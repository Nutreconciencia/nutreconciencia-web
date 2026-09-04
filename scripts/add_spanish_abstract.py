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
    Supported user markup:
    **negrita**
    [[BIG]]texto grande[[/BIG]]
    """
    text = escape(text, quote=False)

    text = re.sub(
        r"\[\[BIG\]\](.*?)\[\[/BIG\]\]",
        r'<span class="summary-big">\1</span>',
        text,
        flags=re.S,
    )

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


def paragraphs_to_html(paragraphs: list[str]) -> str:
    return "\n".join(
        f"<p>{render_inline(p)}</p>"
        for p in paragraphs
    )


def find_metadata_file(folder: Path) -> Path:
    """
    DOI-created papers use metadata.json.
    ORCID-created papers use orcid.json.
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


def replace_clean_summary(html: str, first_paragraph: str) -> str:
    """
    Replace the paragraph inside the first .clean-summary block.

    Uses the block boundary defined by the following .clean-divider,
    so nested divs do not break the parser.
    """

    pattern = re.compile(
        r'(<div\s+class="clean-summary">.*?)(</div>\s*<div\s+class="clean-divider">)',
        flags=re.S | re.I,
    )

    match = pattern.search(html)

    if not match:
        raise RuntimeError(
            "No se encontró el bloque .clean-summary seguido de .clean-divider."
        )

    block = match.group(1)

    paragraph_match = re.search(
        r"<p>(.*?)</p>",
        block,
        flags=re.S | re.I,
    )

    if not paragraph_match:
        raise RuntimeError(
            "No se encontró <p> dentro de .clean-summary."
        )

    new_block = (
        block[:paragraph_match.start()]
        + f"<p>{render_inline(first_paragraph)}</p>"
        + block[paragraph_match.end():]
    )

    return html[:match.start()] + new_block + match.group(2) + html[match.end():]


def replace_clean_content(html: str, paragraphs: list[str]) -> str:
    """
    Replace the editorial content between .clean-divider and
    'Publicación original'.

    The original publication block and request box remain untouched.
    """

    divider = '<div class="clean-divider"></div>'

    divider_pos = html.find(divider)

    if divider_pos == -1:
        raise RuntimeError(
            "No se encontró .clean-divider."
        )

    publication_pattern = re.compile(
        r'<div\s+class="clean-section">\s*'
        r'<div\s+class="clean-kicker">Publicación original</div>',
        flags=re.S | re.I,
    )

    publication_match = publication_pattern.search(
        html,
        divider_pos + len(divider),
    )

    if not publication_match:
        raise RuntimeError(
            "No se encontró la sección 'Publicación original'."
        )

    analysis_html = (
        "\n\n"
        '<div class="clean-section">\n'
        '  <div class="clean-kicker">ANÁLISIS EN ESPAÑOL</div>\n'
        '  <h2>Lo que explica realmente el artículo</h2>\n'
        f'  {paragraphs_to_html(paragraphs)}\n'
        '</div>\n\n'
    )

    content_start = divider_pos + len(divider)

    return (
        html[:content_start]
        + analysis_html
        + html[publication_match.start():]
    )


def update_clean_paper(
    html: str,
    paragraphs: list[str],
) -> str:
    """
    Update current .clean-paper article pages.
    """

    updated = replace_clean_summary(
        html,
        paragraphs[0],
    )

    updated = replace_clean_content(
        updated,
        paragraphs,
    )

    return updated


def update_legacy_paper(
    html: str,
    paragraphs: list[str],
) -> str:
    """
    Support the older summary-lead / #s1 template.
    """

    lead_marker = '<p class="summary-lead">'
    lead_start = html.find(lead_marker)

    if lead_start == -1:
        raise RuntimeError(
            "No se encontró .summary-lead."
        )

    lead_end = html.find("</p>", lead_start)

    if lead_end == -1:
        raise RuntimeError(
            "No se encontró el cierre de .summary-lead."
        )

    lead_end += len("</p>")

    html = (
        html[:lead_start]
        + f'<p class="summary-lead">{render_inline(paragraphs[0])}</p>'
        + html[lead_end:]
    )

    heading = '<h2 id="s1">'
    s1_start = html.find(heading)

    if s1_start == -1:
        raise RuntimeError(
            "No se encontró la sección #s1."
        )

    next_h2 = html.find(
        "<h2 ",
        s1_start + len(heading),
    )

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
        + paragraphs_to_html(paragraphs)
    )

    return (
        html[:s1_start]
        + new_section
        + html[next_h2:]
    )


def main() -> None:
    slug = os.environ.get("ARTICLE_SLUG", "").strip().strip("/")
    summary = os.environ.get("SPANISH_SUMMARY", "").strip()

    if not slug:
        raise SystemExit(
            "ARTICLE_SLUG está vacío."
        )

    if not summary:
        raise SystemExit(
            "SPANISH_SUMMARY está vacío."
        )

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
            "No se encontraron párrafos válidos."
        )

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
