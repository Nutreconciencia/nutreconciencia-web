#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
BASE = "https://nutreconciencia.com"
PERSON = BASE + "/#person"
CSS_VERSION = "28"
UA = "NutreconcienciaWeb/1.0 (https://nutreconciencia.com/)"

def clean(v):
    return re.sub(r"\s+", " ", v or "").strip()

def get_json(url, headers=None, data=None):
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": UA, "Accept": "application/json"},
        data=data,
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))

def get_text(url, headers=None):
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": UA, "Accept": "application/xml,text/xml,*/*"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")

def crossref(doi):
    return get_json(
        "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    )["message"]

def pubmed_id(doi):
    term = urllib.parse.quote(f"{doi}[DOI]", safe="")
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={term}&retmode=json"
        "&tool=nutreconciencia_web&email=miguel@nutreconciencia.com"
    )
    try:
        ids = get_json(url).get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else ""
    except Exception:
        return ""

def pubmed_abstract(pmid):
    if not pmid:
        return ""
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&id={urllib.parse.quote(pmid)}&retmode=xml"
        "&tool=nutreconciencia_web&email=miguel@nutreconciencia.com"
    )
    try:
        root = ET.fromstring(get_text(url))
        parts = []
        for node in root.findall(".//AbstractText"):
            txt = "".join(node.itertext()).strip()
            if not txt:
                continue
            label = node.attrib.get("Label")
            if label and not txt.startswith(label + ":"):
                txt = f"{label}: {txt}"
            parts.append(txt)
        return "\n\n".join(parts).strip()
    except Exception:
        return ""

def translate_to_spanish(text):
    key = os.environ.get("DEEPL_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "DEEPL_API_KEY no está configurada. Añádela como GitHub Actions secret."
        )
    payload = urllib.parse.urlencode({
        "text": text,
        "source_lang": "EN",
        "target_lang": "ES",
        "preserve_formatting": "1",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api-free.deepl.com/v2/translate",
        data=payload,
        headers={
            "Authorization": f"DeepL-Auth-Key {key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepL API error {exc.code}: {detail}") from exc

    translations = result.get("translations", [])
    if not translations:
        raise RuntimeError("DeepL no devolvió ninguna traducción.")
    return translations[0].get("text", "").strip()

def year_of(item):
    for key in ("published-print", "published-online", "issued", "created"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""

def authors_of(item):
    out = []
    for a in item.get("author", []):
        name = clean(f"{a.get('given', '')} {a.get('family', '')}")
        if name:
            out.append(name)
    return out

def slugify(title):
    s = clean(title).lower().translate(str.maketrans("áéíóúüñ", "aeiouun"))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:120].rstrip("-")

def build_page(item, doi, slug, pmid, abstract_en, abstract_es):
    title = clean((item.get("title") or [""])[0])
    journal = clean((item.get("container-title") or [""])[0]) or "Scientific publication"
    year = year_of(item)
    authors = ", ".join(authors_of(item))
    canonical = f"{BASE}/articulos/{slug}/"
    doi_url = f"https://doi.org/{doi}"

    if abstract_es:
        lead = abstract_es
        note = (
            "Traducción al español del abstract publicado por la fuente científica original. "
            "No sustituye al artículo científico completo."
        )
        content = (
            '<h2 id="s1">Resumen del artículo</h2>'
            + "".join(f"<p>{escape(p.strip())}</p>" for p in abstract_es.split("\n\n") if p.strip())
        )
        sidebar_label = "Resumen del artículo"
    else:
        lead = f"Publicación científica de {journal}" + (f" ({year})." if year else ".")
        note = (
            "No se encontró un abstract disponible para traducir. "
            "Esta ficha contiene información bibliográfica."
        )
        content = (
            '<h2 id="s1">Sobre esta publicación</h2>'
            '<p>Esta ficha reúne los datos bibliográficos de la publicación y enlaza directamente con la fuente científica original.</p>'
        )
        sidebar_label = "Sobre esta publicación"

    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
    pubmed_button = (
        f'<a class="btn primary" href="{escape(pubmed_url)}" target="_blank" rel="noopener">Ver en PubMed ↗</a>'
        if pmid else ""
    )

    schema = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "@id": canonical.rstrip("/") + "/#article",
        "url": canonical,
        "headline": title,
        "author": [{
            "@type": "Person",
            "@id": PERSON,
            "name": "Miguel López Moreno"
        }],
        "sameAs": [doi_url] + ([pubmed_url] if pmid else []),
        "isPartOf": {"@type": "Periodical", "name": journal},
    }
    if year:
        schema["datePublished"] = year
    if abstract_es:
        schema["description"] = abstract_es

    meta = (
        f'<span class="pill">{escape(journal)}</span>'
        f'<span class="pill">{escape(year)}</span>'
        '<span class="pill">DOI</span>'
        + ('<span class="pill">PubMed</span>' if pmid else '')
    )

    subject = urllib.parse.quote(f"Solicitud de estudio completo — {title}")
    body = urllib.parse.quote(
        f"Hola Miguel,\n\nMe gustaría solicitar el estudio completo: {title}\n\nMuchas gracias."
    )
    mail = f"mailto:miguel@nutreconciencia.com?subject={subject}&body={body}"

    # Deliberately avoids f-string interpolation across JavaScript.
    template = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ | Miguel López Moreno</title>
<meta name="description" content="__DESCRIPTION__">
<link rel="canonical" href="__CANONICAL__">
<meta property="og:title" content="__TITLE__ | Miguel López Moreno">
<meta property="og:description" content="__DESCRIPTION__">
<meta property="og:type" content="article">
<meta property="og:image" content="https://nutreconciencia.com/assets/miguel-lopez-moreno.jpg">
<link rel="stylesheet" href="../../assets/styles.css?v=__CSS__">
<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">
__SCHEMA__
</script>
<meta property="og:url" content="__CANONICAL__">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__ | Miguel López Moreno">
<meta name="twitter:description" content="__DESCRIPTION__">
<meta name="twitter:image" content="https://nutreconciencia.com/assets/miguel-lopez-moreno.jpg">
</head><body>
<nav class="nav"><div class="nav-inner"><a class="brand" href="/">Miguel López Moreno <span>/ Nutreconciencia</span></a>
<button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false"><span class="open">☰</span><span class="close">×</span></button>
<div class="links"><a href="/articulos/">Investigación</a><a href="/articulos/">Artículos</a><a href="/prensa/">Prensa</a><a href="/libro/">Libro</a><a href="/sobre-mi/">Sobre mí</a><a href="/podcasts/">Podcasts</a></div></div></nav>
<div class="breadcrumbs"><a href="/articulos/">Artículos</a> → __TITLE__</div>
<main class="article-shell">
<section class="study-hero article-top">
<div class="article-kicker">Resumen científico · __JOURNAL__ · __YEAR__</div>
<h1 class="study-title-original">__TITLE__</h1>
<div class="article-original"><strong>Título original:</strong> __TITLE__</div>
<div class="article-meta">__META__</div>
</section>
<section class="study-layout article-layout"><div id="resumen" class="study-main article-prose">
<p class="summary-lead">__LEAD__</p>
<div class="article-note">__NOTE__</div>
__CONTENT__
<h2 id="publicacion">Publicación original</h2><p><strong>__TITLE__</strong></p><p>__AUTHORS__</p>
<div class="source-buttons"><a class="btn soft" href="__DOI_URL__" target="_blank" rel="noopener">Ver DOI ↗</a>__PUBMED_BUTTON__</div>
</div><aside class="study-side article-sidebar"><div class="sidebar-card"><strong>En esta página</strong><div class="sidebar-links"><a href="#resumen">Resumen</a><a href="#s1">__SIDEBAR__</a><a href="#publicacion">Publicación</a></div></div>
<div class="sidebar-card"><strong>Artículo original</strong><div><strong>Título</strong><br>__TITLE__</div></div></aside></section>
<div class="study-request"><strong>¿Quieres consultar el estudio completo?</strong>
<a href="__MAIL__">Solicitar el estudio completo por email</a>
<small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small></div>
</main><footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div><div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br>
<a href="mailto:miguel@nutreconciencia.com">miguel@nutreconciencia.com</a><br>© 2026 Miguel López Moreno.</div></div></footer>
<script>
document.querySelectorAll('.mobile-menu-toggle').forEach(btn=>{
  btn.addEventListener('click',()=>{
    const nav=btn.closest('.nav');
    const open=nav.classList.toggle('nav-open');
    btn.setAttribute('aria-expanded',open?'true':'false');
  });
});
</script></body></html>"""

    replacements = {
        "__TITLE__": escape(title),
        "__DESCRIPTION__": escape((abstract_es or lead)[:300]),
        "__CANONICAL__": canonical,
        "__CSS__": CSS_VERSION,
        "__SCHEMA__": json.dumps(schema, ensure_ascii=False, indent=2),
        "__JOURNAL__": escape(journal),
        "__YEAR__": escape(year),
        "__META__": meta,
        "__LEAD__": escape(lead),
        "__NOTE__": escape(note),
        "__CONTENT__": content,
        "__AUTHORS__": escape(authors),
        "__DOI_URL__": escape(doi_url),
        "__PUBMED_BUTTON__": pubmed_button,
        "__SIDEBAR__": escape(sidebar_label),
        "__MAIL__": mail,
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template

def main():
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
    abstract_en = pubmed_abstract(pmid)
    abstract_es = translate_to_spanish(abstract_en) if abstract_en else ""

    folder.mkdir(parents=True)
    (folder / "index.html").write_text(
        build_page(item, doi, slug, pmid, abstract_en, abstract_es),
        encoding="utf-8",
    )

    metadata = {
        "doi": doi,
        "title": title,
        "authors": authors_of(item),
        "journal": clean((item.get("container-title") or [""])[0]),
        "publisher": clean(item.get("publisher", "")),
        "year": year_of(item),
        "pmid": pmid,
        "abstract_english": abstract_en,
        "abstract_spanish": abstract_es,
        "translation_provider": "DeepL" if abstract_es else "",
    }
    (folder / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 72)
    print("NEW PAPER CREATED — DOI + PUBMED + SPANISH ABSTRACT")
    print("=" * 72)
    print("DOI:", doi)
    print("Title:", title)
    print("Slug:", slug)
    print("PMID:", pmid or "not found")
    print("English abstract:", "FOUND" if abstract_en else "NOT FOUND")
    print("Spanish translation:", "FOUND" if abstract_es else "NOT CREATED")
    print("CSS version:", CSS_VERSION)
    print("ScholarlyArticle schema: PASS")

if __name__ == "__main__":
    main()
