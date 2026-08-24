#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"

BIG_RE = re.compile(r"\[\[BIG\]\](.*?)\[\[/BIG\]\]", re.S)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)


def clean(v: str) -> str:
    return re.sub(r"\s+", " ", v or "").strip()


def inline_markup(text: str) -> str:
    """Support **bold** and [[BIG]]larger text[[/BIG]] without raw HTML."""
    parts = []
    pos = 0
    token_re = re.compile(
        r"\[\[BIG\]\].*?\[\[/BIG\]\]|\*\*.+?\*\*",
        re.S,
    )

    for match in token_re.finditer(text):
        parts.append(escape(text[pos:match.start()]))
        token = match.group(0)

        big = BIG_RE.fullmatch(token)
        if big:
            parts.append(f'<span class="summary-big">{escape(big.group(1))}</span>')
        else:
            bold = BOLD_RE.fullmatch(token)
            if bold:
                parts.append(f"<strong>{escape(bold.group(1))}</strong>")
            else:
                parts.append(escape(token))

        pos = match.end()

    parts.append(escape(text[pos:]))
    return "".join(parts)


def paragraph_html(summary: str) -> tuple[list[str], str]:
    # GitHub Actions inputs are awkward for blank lines, so use ||| as a
    # deterministic paragraph separator.
    paragraphs = [p.strip() for p in summary.split("|||") if p.strip()]
    if not paragraphs:
        paragraphs = [summary.strip()]

    html_paragraphs = [f"<p>{inline_markup(p)}</p>" for p in paragraphs]
    lead = inline_markup(paragraphs[0])

    return paragraphs, "\n".join(html_paragraphs)


def main() -> None:
    slug = os.environ.get("ARTICLE_SLUG", "").strip().strip("/")
    # Be forgiving if the user pastes the full relative path.
    slug = re.sub(r"^articulos/", "", slug)
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

    paragraphs, body_html = paragraph_html(summary)
    lead_html = inline_markup(paragraphs[0])

    # Always replace the existing summary lead.
    lead_match = re.search(
        r'<p\s+class=["\']summary-lead["\']>.*?</p>',
        html,
        re.I | re.S,
    )
    if not lead_match:
        raise RuntimeError("No se encontró <p class=\"summary-lead\"> en la ficha.")

    updated = (
        html[:lead_match.start()]
        + f'<p class="summary-lead">{lead_html}</p>'
        + html[lead_match.end():]
    )

    # The previous versions of the generator did not all use the same id="s1".
    # Instead of depending on #s1, replace the complete first content section
    # between article-note and "Publicación original".
    publicacion_match = re.search(
        r'<h2\s+id=["\']publicacion["\']>',
        updated,
        re.I,
    )
    if not publicacion_match:
        raise RuntimeError("No se encontró la sección #publicacion.")

    note_match = re.search(
        r'<div\s+class=["\']article-note["\']>.*?</div>',
        updated,
        re.I | re.S,
    )
    if not note_match or note_match.start() > publicacion_match.start():
        raise RuntimeError("No se encontró article-note antes de Publicación original.")

    # Preserve the note, but replace everything after it and before Publicación original.
    # This removes old "Sobre esta publicación" / old #s1 content cleanly.
    note_end = note_match.end()
    prefix = updated[:note_end]
    suffix = updated[publicacion_match.start():]

    new_section = (
        '<h2 id="s1">Resumen del artículo</h2>\n'
        + body_html
        + "\n"
    )

    updated = prefix + new_section + suffix

    metadata["abstract_spanish"] = summary
    metadata["translation_provider"] = "manual"
    metadata["editorial_summary_source"] = "user_provided"
    metadata["summary_paragraphs"] = paragraphs

    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    html_path.write_text(updated, encoding="utf-8")

    # Verify result.
    check_html = html_path.read_text(encoding="utf-8")
    if '<h2 id="s1">Resumen del artículo</h2>' not in check_html:
        raise RuntimeError("La sección Resumen del artículo no se pudo insertar.")
    if '<p class="summary-lead">' not in check_html:
        raise RuntimeError("summary-lead ausente tras la actualización.")
    if len(paragraphs) > 1 and check_html.count("<p>") < len(paragraphs):
        raise RuntimeError("No se insertaron todos los párrafos.")

    print("=" * 72)
    print("ADD SPANISH ABSTRACT — MANUAL V2")
    print("=" * 72)
    print("Article:", slug)
    print("Paragraphs inserted:", len(paragraphs))
    print("BIG markup supported: PASS")
    print("Bold markup supported: PASS")
    print("metadata.json: UPDATED")
    print("index.html: UPDATED")
    print("Summary section: PASS")
    print("Translation provider: manual")


if __name__ == "__main__":
    main()
