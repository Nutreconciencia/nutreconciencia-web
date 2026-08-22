#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
BASE = "https://nutreconciencia.com"
UA = "NutreconcienciaWeb/1.0 (https://nutreconciencia.com/)"
CSS_VERSION = "28"


def clean(v: str | None) -> str:
    return re.sub(r"\s+", " ", v or "").strip()


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def crossref(doi: str) -> dict:
    return get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe=""))["message"]


def pubmed_id(doi: str) -> str:
    term = urllib.parse.quote(f"{doi}[DOI]", safe="")
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=" + term + "&retmode=json"
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
    out = []
    for a in item.get("author", []):
        name = clean(f"{a.get('given','')} {a.get('family','')}")
        if name:
            out.append(name)
    return out


def abstract_from_crossref(item: dict) -> str:
    raw = clean(item.get("abstract", ""))
    if not raw:
        return ""
    # Crossref abstracts frequently include JATS/XML tags.
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return clean(raw)


def slugify(s: str) -> str:
    trans = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    s = clean(s).translate(trans).lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:120]


def editorial_sections(title: str, journal: str, abstract: str) -> list[tuple[str, str]]:
    # Do not invent paper-specific claims. Use the publisher abstract verbatim as
    # the evidence base, organized into the same editorial structure.
    if not abstract:
        return [("Sobre esta publicación", f"Esta ficha reúne los datos bibliográficos de una publicación científica de {journal} y enlaza directamente con la fuente original.")]

    # Generic but source-grounded structure; no claims are added beyond the abstract.
    return [
        ("Resumen", abstract),
        ("Publicación", f"El artículo fue publicado en {journal} bajo el título “{title}”.")
    ]


def build_page(item: dict, doi: str, pmid: str) -> str:
    title = clean((item.get("title") or [""])[0])
    journal = clean((item.get("container-title") or [""])[0]) or "Scientific publication"
    year = year_of(item)
    authors = authors_of(item)
    abstract = abstract_from_crossref(item)
    canonical = f"{BASE}/articulos/{slugify(title)}/"
    slug = slugify(title)
    doi_url = f"https://doi.org/{doi}"
    pmid_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

    description = (abstract[:280] + "…") if len(abstract) > 280 else (abstract or f"Publicación científica de {journal} ({year}).")
    schema = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "@id": canonical.rstrip("/") + "/#article",
        "url": canonical,
        "headline": title,
        "author": [{"@type":"Person", "@id":BASE+"/#person", "name":"Miguel López Moreno"}],
        "sameAs": [doi_url] + ([pmid_url] if pmid else []),
        "isPartOf": {"@type":"Periodical", "name":journal}
    }
    if year:
        schema["datePublished"] = year

    pills = (
        f'<span class="pill">{html.escape(journal)}</span>'
        f'<span class="pill">{html.escape(year)}</span>'
        f'<span class="pill">DOI</span>'
        + (f'<span class="pill">PubMed</span>' if pmid else "")
    )
    pubmed_button = (
        f'<a class="btn primary" href="{html.escape(pmid_url)}" target="_blank" rel="noopener">Ver en PubMed ↗</a>'
        if pmid else ""
    )
    sections = editorial_sections(title, journal, abstract)
    section_html = []
    nav_links = []
    for idx, (heading, body) in enumerate(sections):
        sec_id = "resumen" if idx == 0 else f"s{idx}"
        nav_links.append(f'<a href="#{sec_id}">{html.escape(heading)}</a>')
        section_html.append(f'<h2 id="{sec_id}">{html.escape(heading)}</h2><p>{html.escape(body)}</p>')

    nav_links.append('<a href="#publicacion">Publicación</a>')
    subject = urllib.parse.quote(f"Solicitud de estudio completo — {title}")
    body = urllib.parse.quote(f"Hola Miguel,\n\nMe gustaría solicitar el estudio completo: {title}\n\nMuchas gracias.")
    mail = f"mailto:miguel@nutreconciencia.com?subject={subject}&body={body}"

    return f'''<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} | Miguel López Moreno</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(title)} | Miguel López Moreno"><meta property="og:description" content="{html.escape(description)}">
<meta property="og:type" content="article"><meta property="og:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
<link rel="stylesheet" href="../../assets/styles.css?v={CSS_VERSION}">
<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>
<meta property="og:url" content="{canonical}"><meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(title)} | Miguel López Moreno"><meta name="twitter:description" content="{html.escape(description)}">
<meta name="twitter:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
</head><body>
<nav class="nav"><div class="nav-inner"><a class="brand" href="/">Miguel López Moreno <span>/ Nutreconciencia</span></a>
<button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false"><span class="open">☰</span><span class="close">×</span></button>
<div class="links"><a href="/articulos/">Investigación</a><a href="/articulos/">Artículos</a><a href="/prensa/">Prensa</a><a href="/libro/">Libro</a><a href="/sobre-mi/">Sobre mí</a><a href="/podcasts/">Podcasts</a></div></div></nav>
<div class="breadcrumbs"><a href="/articulos/">Artículos</a> → {html.escape(title)}</div>
<main class="article-shell">
<section class="study-hero article-top"><div class="article-kicker">Resumen científico · {html.escape(journal)} · {html.escape(year)}</div>
<h1 class="study-title-original">{html.escape(title)}</h1>
<div class="article-original"><strong>Título original:</strong> {html.escape(title)}</div>
<div class="article-meta">{pills}</div></section>
<section class="study-layout article-layout"><div id="resumen" class="study-main article-prose">
<p class="summary-lead">{html.escape(abstract[:700]) if abstract else html.escape(description)}</p>
<div class="article-note">Este resumen está basado en la información publicada por la fuente científica original y no sustituye al artículo completo.</div>
{''.join(section_html)}
<h2 id="publicacion">Publicación original</h2><p><strong>{html.escape(title)}</strong></p><p>{html.escape(', '.join(authors))}</p>
<div class="source-buttons"><a class="btn soft" href="{doi_url}" target="_blank" rel="noopener">Ver DOI ↗</a>{pubmed_button}</div>
</div><aside class="study-side article-sidebar"><div class="sidebar-card"><strong>En esta página</strong><div class="sidebar-links">{''.join(nav_links)}</div></div>
<div class="sidebar-card"><strong>Artículo original</strong><div><strong>Título</strong><br>{html.escape(title)}</div></div></aside></section>
<div class="study-request"><strong>¿Quieres consultar el estudio completo?</strong><a href="{mail}">Solicitar el estudio completo por email</a><small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small></div>
</main>
<footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div><div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br><a href="mailto:miguel@nutreconciencia.com">miguel@nutreconciencia.com</a><br>© 2026 Miguel López Moreno.</div></div></footer>
<script>document.querySelectorAll('.mobile-menu-toggle').forEach(btn=>{{btn.addEventListener('click',()=>{{const nav=btn.closest('.nav');const open=nav.classList.toggle('nav-open');btn.setAttribute('aria-expanded',open?'true':'false');}});}});</script>
</body></html>'''


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python scripts/add_paper_by_doi.py DOI")
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
    (folder / "index.html").write_text(build_page(item, doi, pmid), encoding="utf-8")
    (folder / "metadata.json").write_text(json.dumps({
        "doi":doi,"title":title,"authors":authors_of(item),"journal":clean((item.get("container-title") or [""])[0]),
        "publisher":clean(item.get("publisher","")),"year":year_of(item),"pmid":pmid,
        "abstract":abstract_from_crossref(item)
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("NEW PAPER CREATED — FINAL EDITORIAL TEMPLATE")
    print("DOI:",doi)
    print("Title:",title)
    print("Slug:",slug)
    print("Journal:",clean((item.get("container-title") or [""])[0]))
    print("PMID:",pmid or "not found")
    print("Abstract from Crossref:","YES" if abstract_from_crossref(item) else "NO")
    print("CSS version:",CSS_VERSION)

if __name__ == "__main__":
    main()
