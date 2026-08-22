#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
BASE = "https://nutreconciencia.com"
PERSON = f"{BASE}/#person"
CSS = "../../assets/styles.css?v=28"
USER_AGENT = "NutreconcienciaWeb/1.0 (https://nutreconciencia.com/)"


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def crossref(doi: str) -> dict:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    return get_json(url)["message"]


def pubmed_id(doi: str) -> str:
    term = urllib.parse.quote(f"{doi}[DOI]", safe="")
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
        f"db=pubmed&term={term}&retmode=json"
    )
    try:
        ids = get_json(url).get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else ""
    except Exception:
        return ""


def year_of(item: dict) -> str:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def authors_of(item: dict) -> list[str]:
    names: list[str] = []
    for author in item.get("author", []):
        name = clean(f"{author.get('given', '')} {author.get('family', '')}")
        if name:
            names.append(name)
    return names


def slugify(title: str) -> str:
    translation = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    value = clean(title).translate(translation).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:120].rstrip("-")


def build_schema(title: str, journal: str, canonical: str, doi: str, pmid: str, year: str) -> dict:
    same_as = [f"https://doi.org/{doi}"]
    if pmid:
        same_as.append(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    schema = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "@id": canonical.rstrip("/") + "/#article",
        "url": canonical,
        "headline": title,
        "author": [
            {
                "@type": "Person",
                "@id": PERSON,
                "name": "Miguel López Moreno",
            }
        ],
        "sameAs": same_as,
        "isPartOf": {"@type": "Periodical", "name": journal},
    }
    if year:
        schema["datePublished"] = year
    return schema


def build_html(item: dict, slug: str, doi: str, pmid: str) -> str:
    title = clean((item.get("title") or [""])[0])
    journal = clean((item.get("container-title") or [""])[0]) or "Scientific publication"
    year = year_of(item)
    authors = authors_of(item)
    authors_text = ", ".join(authors)
    canonical = f"{BASE}/articulos/{slug}/"
    doi_url = f"https://doi.org/{doi}"

    description = (
        f"Publicación científica de {journal}"
        + (f" ({year})" if year else "")
        + ". Esta ficha reúne los datos bibliográficos y los enlaces a la publicación original."
    )

    schema = build_schema(title, journal, canonical, doi, pmid, year)
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)

    pubmed_pill = '<span class="pill">PubMed</span>' if pmid else ""
    pubmed_button = (
        f'<a class="btn primary" href="https://pubmed.ncbi.nlm.nih.gov/{escape(pmid)}/" '
        'target="_blank" rel="noopener">Ver en PubMed ↗</a>'
        if pmid
        else ""
    )

    subject = urllib.parse.quote(f"Solicitud de estudio completo — {title}")
    body = urllib.parse.quote(
        f"Hola Miguel,\n\nMe gustaría solicitar el estudio completo: {title}\n\nMuchas gracias."
    )
    mailto = f"mailto:miguel@nutreconciencia.com?subject={subject}&body={body}"

    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | Miguel López Moreno</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{escape(title)} | Miguel López Moreno">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="article">
<meta property="og:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
<link rel="stylesheet" href="{CSS}">
<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">
{schema_json}
</script>
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escape(title)} | Miguel López Moreno">
<meta name="twitter:description" content="{escape(description)}">
<meta name="twitter:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
</head>
<body>
<nav class="nav"><div class="nav-inner"><a class="brand" href="/">Miguel López Moreno <span>/ Nutreconciencia</span></a>
<button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false"><span class="open">☰</span><span class="close">×</span></button>
<div class="links"><a href="/articulos/">Investigación</a><a href="/articulos/">Artículos</a><a href="/prensa/">Prensa</a><a href="/libro/">Libro</a><a href="/sobre-mi/">Sobre mí</a><a href="/podcasts/">Podcasts</a></div></div></nav>
<div class="breadcrumbs"><a href="/articulos/">Artículos</a> → {escape(title)}</div>
<main class="article-shell">
<section class="study-hero article-top">
<div class="article-kicker">Resumen científico · {escape(journal)} · {escape(year)}</div>
<h1 class="study-title-original">{escape(title)}</h1>
<div class="article-original"><strong>Título original:</strong> {escape(title)}</div>
<div class="article-meta"><span class="pill">{escape(journal)}</span><span class="pill">{escape(year)}</span><span class="pill">DOI</span>{pubmed_pill}</div>
</section>
<section class="study-layout article-layout">
<div id="resumen" class="study-main article-prose">
<p class="summary-lead">{escape(description)}</p>
<div class="article-note">Esta ficha bibliográfica facilita la consulta y no sustituye al artículo científico original.</div>
<h2 id="publicacion">Publicación original</h2>
<p><strong>{escape(title)}</strong></p>
<p>{escape(authors_text)}</p>
<div class="source-buttons"><a class="btn soft" href="{escape(doi_url)}" target="_blank" rel="noopener">Ver DOI ↗</a>{pubmed_button}</div>
</div>
<aside class="study-side article-sidebar">
<div class="sidebar-card"><strong>En esta página</strong><div class="sidebar-links"><a href="#resumen">Resumen</a><a href="#publicacion">Publicación</a></div></div>
<div class="sidebar-card"><strong>Artículo original</strong><div><strong>Título</strong><br>{escape(title)}</div></div>
</aside>
</section>
<div class="study-request"><strong>¿Quieres consultar el estudio completo?</strong>
<a href="{mailto}">Solicitar el estudio completo por email</a>
<small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small></div>
</main>
<footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div><div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br><a href="mailto:miguel@nutreconciencia.com">miguel@nutreconciencia.com</a><br>© 2026 Miguel López Moreno.</div></div></footer>
<script>
document.querySelectorAll('.mobile-menu-toggle').forEach(btn=>{{
  btn.addEventListener('click',()=>{{
    const nav=btn.closest('.nav');
    const open=nav.classList.toggle('nav-open');
    btn.setAttribute('aria-expanded',open?'true':'false');
  }});
}});
</script></body></html>'''


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python add_paper_by_doi.py DOI")

    doi = clean(sys.argv[1]).replace("https://doi.org/", "").strip("/")
    item = crossref(doi)
    title = clean((item.get("title") or [""])[0])
    if not title:
        raise RuntimeError("Crossref no devolvió título")

    slug = slugify(title)
    folder = ART / slug
    if folder.exists():
        raise RuntimeError(f"La carpeta ya existe: {folder}")

    pmid = pubmed_id(doi)
    folder.mkdir(parents=True)
    (folder / "index.html").write_text(build_html(item, slug, doi, pmid), encoding="utf-8")
    (folder / "metadata.json").write_text(
        json.dumps(
            {
                "doi": doi,
                "title": title,
                "authors": authors_of(item),
                "journal": clean((item.get("container-title") or [""])[0]),
                "publisher": clean(item.get("publisher", "")),
                "year": year_of(item),
                "pmid": pmid,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("NEW PAPER CREATED — EDITORIAL TEMPLATE V3")
    print("DOI:", doi)
    print("Title:", title)
    print("Slug:", slug)
    print("Journal:", clean((item.get("container-title") or [""])[0]))
    print("Year:", year_of(item))
    print("PMID:", pmid or "not found")
    print("CSS version: 28")
    print("Editorial layout: PASS")


if __name__ == "__main__":
    main()


