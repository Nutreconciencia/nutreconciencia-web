#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"


# ---------------------------------------------------------------------
# MARKUP
# ---------------------------------------------------------------------

def render_inline(text: str) -> str:
    """
    Supported editorial markup:

    **texto**                      -> <strong>texto</strong>
    [[BIG]]texto[[/BIG]]           -> <span class="summary-big">texto</span>
    """

    text = escape(text, quote=False)

    # BIG
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


def render_paragraph_or_heading(text: str) -> str:
    """
    Supported block markup:

    [[HEADING]]Título[[/HEADING]]
    texto normal
    """

    text = text.strip()

    heading = re.fullmatch(
        r"\[\[HEADING\]\](.*?)\[\[/HEADING\]\]",
        text,
        flags=re.S,
    )

    if heading:
        title = render_inline(heading.group(1).strip())

        return (
            '<h3 class="summary-heading">'
            f"{title}"
            "</h3>"
        )

    return f"<p>{render_inline(text)}</p>"


def split_paragraphs(summary: str) -> list[str]:
    """
    Main separator:
        |||

    Fallback:
        blank lines
    """

    if "|||" in summary:
        parts = summary.split("|||")
    else:
        parts = re.split(r"\n\s*\n", summary)

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def paragraphs_to_html(paragraphs: list[str]) -> str:
    return "\n".join(
        render_paragraph_or_heading(part)
        for part in paragraphs
    )


# ---------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------

def find_metadata_file(folder: Path) -> Path:
    """
    DOI-generated articles:
        metadata.json

    ORCID-managed articles:
        orcid.json
    """

    metadata_path = folder / "metadata.json"
    orcid_path = folder / "orcid.json"

    if metadata_path.exists():
        return metadata_path

    if orcid_path.exists():
        return orcid_path

    raise FileNotFoundError(
        "No se encontró metadata.json ni orcid.json en:\n"
        f"{folder}"
    )


# ---------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------

def ensure_summary_css(html: str) -> str:
    """
    Injects the editorial heading styles into the page if they are not
    already present.

    This avoids depending on styles.css for the new summary markup.
    """

    if ".summary-heading" in html:
        return html

    css = """
<style id="summary-editorial-styles">
.summary-heading {
  max-width: 760px;
  margin: 46px 0 15px;
  font-family: "Source Serif 4", Georgia, "Times New Roman", serif;
  font-size: clamp(1.55rem, 2.8vw, 2.2rem);
  line-height: 1.12;
  letter-spacing: -0.015em;
  font-weight: 500;
}

.summary-heading:first-child {
  margin-top: 0;
}

.summary-big {
  display: inline-block;
  margin: 7px 0;
  font-family: "Source Serif 4", Georgia, "Times New Roman", serif;
  font-size: clamp(1.3rem, 2.5vw, 1.8rem);
  line-height: 1.18;
  font-weight: 500;
}

.clean-section .summary-heading,
.clean-section .summary-big {
  color: inherit;
}

.clean-section .summary-heading + p {
  margin-top: 0;
}

@media (max-width: 700px) {
  .summary-heading {
    margin-top: 38px;
    font-size: 1.55rem;
  }

  .summary-big {
    font-size: 1.3rem;
  }
}
</style>
"""

    head_end = re.search(
        r"</head>",
        html,
        flags=re.I,
    )

    if not head_end:
        raise RuntimeError(
            "No se encontró </head> para insertar los estilos."
        )

    return (
        html[:head_end.start()]
        + css
        + "\n"
        + html[head_end.start():]
    )


# ---------------------------------------------------------------------
# CLEAN PAPER TEMPLATE
# ---------------------------------------------------------------------

def replace_clean_summary(
    html: str,
    first_paragraph: str,
) -> str:
    """
    Replace only the paragraph inside .clean-summary.

    IMPORTANT:
    We do not assume where the closing </div> is because the block
    contains nested divs.
    """

    pattern = re.compile(
        r'<div\s+class="clean-summary">'
        r'.*?'
        r'<p>(.*?)</p>'
        r'.*?'
        r'</div>\s*'
        r'<div\s+class="clean-divider">',
        flags=re.S | re.I,
    )

    match = pattern.search(html)

    if not match:
        raise RuntimeError(
            "No se encontró el bloque .clean-summary "
            "seguido de .clean-divider."
        )

    old_paragraph = match.group(1)

    new_paragraph = render_inline(
        first_paragraph
    )

    block = match.group(0)

    block = block.replace(
        f"<p>{old_paragraph}</p>",
        f"<p>{new_paragraph}</p>",
        1,
    )

    return (
        html[:match.start()]
        + block
        + html[match.end():]
    )


def find_publication_section(
    html: str,
    start_pos: int,
) -> re.Match[str] | None:

    pattern = re.compile(
        r'<div\s+class="clean-section">\s*'
        r'<div\s+class="clean-kicker">\s*'
        r'Publicación original\s*'
        r'</div>',
        flags=re.S | re.I,
    )

    return pattern.search(
        html,
        start_pos,
    )


def replace_clean_content(
    html: str,
    paragraphs: list[str],
) -> str:
    """
    Replace the automatically generated editorial sections between
    .clean-divider and "Publicación original".
    """

    divider = '<div class="clean-divider"></div>'

    divider_pos = html.find(divider)

    if divider_pos == -1:
        raise RuntimeError(
            "No se encontró .clean-divider."
        )

    publication_match = find_publication_section(
        html,
        divider_pos + len(divider),
    )

    if publication_match is None:
        raise RuntimeError(
            "No se encontró la sección 'Publicación original'."
        )

    editorial_html = (
        "\n\n"
        '<div class="clean-section">\n'
        '  <div class="clean-kicker">'
        'ANÁLISIS EN ESPAÑOL'
        '</div>\n'
        '  <h2>¿Qué nos enseña realmente esta revisión?</h2>\n'
        f'  {paragraphs_to_html(paragraphs)}\n'
        '</div>\n\n'
    )

    content_start = (
        divider_pos
        + len(divider)
    )

    return (
        html[:content_start]
        + editorial_html
        + html[publication_match.start():]
    )


def update_clean_paper(
    html: str,
    paragraphs: list[str],
) -> str:

    updated = ensure_summary_css(html)

    updated = replace_clean_summary(
        updated,
        paragraphs[0],
    )

    updated = replace_clean_content(
        updated,
        paragraphs,
    )

    return updated


# ---------------------------------------------------------------------
# LEGACY TEMPLATE
# ---------------------------------------------------------------------

def update_legacy_paper(
    html: str,
    paragraphs: list[str],
) -> str:
    """
    Legacy template:

        <p class="summary-lead">
        ...
        <h2 id="s1">
    """

    lead_marker = '<p class="summary-lead">'

    lead_start = html.find(
        lead_marker
    )

    if lead_start == -1:
        raise RuntimeError(
            "No se encontró .summary-lead."
        )

    lead_end = html.find(
        "</p>",
        lead_start,
    )

    if lead_end == -1:
        raise RuntimeError(
            "No se encontró el cierre de .summary-lead."
        )

    lead_end += len("</p>")

    new_lead = (
        '<p class="summary-lead">'
        + render_inline(paragraphs[0])
        + "</p>"
    )

    html = (
        html[:lead_start]
        + new_lead
        + html[lead_end:]
    )

    heading = '<h2 id="s1">'

    s1_start = html.find(
        heading
    )

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


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    slug = (
        os.environ
        .get("ARTICLE_SLUG", "")
        .strip()
        .strip("/")
    )

    summary = (
        os.environ
        .get("SPANISH_SUMMARY", "")
        .strip()
    )

    if not slug:
        raise SystemExit(
            "ARTICLE_SLUG está vacío."
        )

    if not summary:
        raise SystemExit(
            "SPANISH_SUMMARY está vacío."
        )

    slug = slug.removeprefix(
        "articulos/"
    )

    folder = ART / slug

    html_path = folder / "index.html"

    if not folder.exists():
        raise FileNotFoundError(
            "No existe la carpeta del artículo:\n"
            f"{folder}"
        )

    if not html_path.exists():
        raise FileNotFoundError(
            "No existe:\n"
            f"{html_path}"
        )

    metadata_path = find_metadata_file(
        folder
    )

    html = html_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    metadata = json.loads(
        metadata_path.read_text(
            encoding="utf-8"
        )
    )

    paragraphs = split_paragraphs(
        summary
    )

    if not paragraphs:
        raise RuntimeError(
            "No se encontraron párrafos válidos."
        )

    # --------------------------------------------------------------
    # Detect template
    # --------------------------------------------------------------

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

    # --------------------------------------------------------------
    # Metadata
    # --------------------------------------------------------------

    metadata["abstract_spanish"] = summary

    metadata["translation_provider"] = "manual"

    metadata["editorial_summary_source"] = (
        "user_provided"
    )

    metadata["summary_paragraphs"] = paragraphs

    metadata["summary_format"] = {
        "paragraph_separator": "|||",
        "bold": "**texto**",
        "large_text": "[[BIG]]texto[[/BIG]]",
        "heading": "[[HEADING]]título[[/HEADING]]",
    }

    # --------------------------------------------------------------
    # Write files
    # --------------------------------------------------------------

    metadata_path.write_text(
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

    # --------------------------------------------------------------
    # Verification
    # --------------------------------------------------------------

    verification_html = html_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    verification_meta = json.loads(
        metadata_path.read_text(
            encoding="utf-8"
        )
    )

    checks = {
        "index.html": html_path.exists(),
        "metadata-file": metadata_path.exists(),
        "spanish-abstract": bool(
            verification_meta.get("abstract_spanish")
        ),
        "manual-source": (
            verification_meta.get(
                "translation_provider"
            )
            == "manual"
        ),
        "editorial-source": (
            verification_meta.get(
                "editorial_summary_source"
            )
            == "user_provided"
        ),
        "paragraph-count": (
            len(
                verification_meta.get(
                    "summary_paragraphs",
                    [],
                )
            )
            == len(paragraphs)
        ),
    }

    for key, ok in checks.items():
        print(
            f"{key}: "
            f"{'PASS' if ok else 'FAIL'}"
        )

        if not ok:
            raise SystemExit(
                f"Verification failed: {key}"
            )

    print("=" * 72)
    print("ADD SPANISH ABSTRACT — MANUAL")
    print("=" * 72)
    print("Article:", slug)
    print("Metadata file:", metadata_path.name)
    print("Template:", template_used)
    print(
        "Paragraphs inserted:",
        len(paragraphs),
    )
    print("metadata file: UPDATED")
    print("index.html: UPDATED")
    print("Translation provider: manual")
    print(
        "Editorial summary source: user_provided"
    )
    print(
        "Editorial headings: SUPPORTED"
    )
    print(
        "Spanish abstract verification: PASS"
    )


if __name__ == "__main__":
    main()
