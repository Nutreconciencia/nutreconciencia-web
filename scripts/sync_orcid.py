#!/usr/bin/env python3
"""
Sync public ORCID works into /articulos/.

- ORCID is the inventory source.
- PubMed is queried by DOI first, then by title.
- Crossref is used as a fallback for metadata.
- If OPENAI_API_KEY is present, a Spanish scientific summary is generated
  via the OpenAI Responses API (model configurable with OPENAI_MODEL).
- Existing manually curated article pages without orcid.json are preserved.
"""
from __future__ import annotations
import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
ORCID = "0000-0003-0553-6210"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")


def get_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Nutreconciencia/2.0 (+https://nutreconciencia.com)",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get_text(url: str, headers: dict | None = None) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Nutreconciencia/2.0 (+https://nutreconciencia.com)",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def val(x):
    return x.get("value", "") if isinstance(x, dict) else (x or "")


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"[^a-z0-9-]", "", text)
    return text[:100].strip("-") or "paper"


def clean_abstract(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def pubmed_search(doi: str, title: str) -> str:
    terms = []
    if doi:
        terms.append(f'"{doi}"[doi]')
    if title:
        terms.append(f'"{title}"[Title]')
    for term in terms:
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(
            {"db": "pubmed", "term": term, "retmode": "xml", "retmax": 3}
        )
        try:
            root = ET.fromstring(get_text(url, {"Accept": "application/xml"}))
            ids = [x.text for x in root.findall(".//Id") if x.text]
            if ids:
                return ids[0]
        except Exception:
            continue
    return ""


def pubmed_record(pmid: str) -> dict:
    if not pmid:
        return {}
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "id": pmid, "retmode": "xml"}
    )
    try:
        root = ET.fromstring(get_text(url, {"Accept": "application/xml"}))
    except Exception:
        return {}
    art = root.find(".//PubmedArticle")
    if art is None:
        return {}
    title = "".join(art.findtext(".//ArticleTitle", default="").split())
    journal = art.findtext(".//Journal/Title", default="")
    year = (
        art.findtext(".//PubDate/Year")
        or art.findtext(".//PubDate/MedlineDate", default="")[:4]
    )
    authors = []
    for au in art.findall(".//AuthorList/Author"):
        last = au.findtext("LastName", default="")
        fore = au.findtext("ForeName", default="")
        collective = au.findtext("CollectiveName", default="")
        name = collective or " ".join(x for x in [fore, last] if x)
        if name:
            authors.append(name)
    parts = []
    for node in art.findall(".//Abstract/AbstractText"):
        txt = "".join(node.itertext()).strip()
        label = node.attrib.get("Label", "").strip()
        if label:
            txt = f"{label}: {txt}"
        if txt:
            parts.append(txt)
    abstract = " ".join(parts)
    doi = ""
    for aid in art.findall(".//PubmedData/ArticleIdList/ArticleId"):
        if aid.attrib.get("IdType") == "doi":
            doi = (aid.text or "").strip()
    return {
        "pmid": pmid,
        "title": title,
        "journal": journal,
        "year": year,
        "authors": authors,
        "abstract": clean_abstract(abstract),
        "doi": doi,
    }


def crossref_record(doi: str) -> dict:
    if not doi:
        return {}
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    try:
        d = get_json(url).get("message", {})
    except Exception:
        return {}
    title = (d.get("title") or [""])[0]
    authors = []
    for a in d.get("author", []):
        n = " ".join(x for x in [a.get("given"), a.get("family")] if x)
        if n:
            authors.append(n)
    issued = d.get("published-print") or d.get("published") or d.get("issued") or {}
    date_parts = (issued.get("date-parts") or [[]])[0]
    year = str(date_parts[0]) if date_parts else ""
    journal = (d.get("container-title") or [""])[0]
    abstract = clean_abstract(d.get("abstract", ""))
    return {
        "title": title,
        "journal": journal,
        "year": year,
        "authors": authors,
        "abstract": abstract,
        "doi": d.get("DOI", doi),
    }


def openai_summary(title: str, abstract: str, journal: str, year: str) -> dict:
    key = os.getenv("OPENAI_API_KEY")
    if not key or not abstract:
        return {}
    prompt = f"""
Eres editor científico de una web personal de investigación en nutrición.
Resume este artículo en CASTELLANO, con precisión y sin inventar resultados.
No uses información que no esté en el abstract. Mantén el título original en su idioma.

Devuelve SOLO JSON válido con estas claves:
lead, question, methods, findings, interpretation, limitations

- lead: 1-2 frases que expliquen por qué importa.
- question: la pregunta principal.
- methods: 1-2 frases sobre diseño/muestra/intervención.
- findings: resultados principales.
- interpretation: qué significa razonablemente.
- limitations: limitaciones o cautelas explícitas en el abstract; si no aparecen, indica que el abstract no las especifica.

Título: {title}
Revista: {journal}
Año: {year}
Abstract:
{abstract}
""".strip()
    body = json.dumps({"model": OPENAI_MODEL, "input": prompt, "temperature": 0.2})
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        raw = get_json("https://api.openai.com/v1/responses", {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }) if False else None
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        print("OpenAI summary failed:", exc)
        return {}
    text = data.get("output_text", "")
    if not text:
        chunks = []
        for item in data.get("output", []):
            for c in item.get("content", []) if isinstance(item, dict) else []:
                if isinstance(c, dict) and c.get("type") == "output_text":
                    chunks.append(c.get("text", ""))
        text = "".join(chunks)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


def journal_brand(journal: str) -> tuple[str, str]:
    x = (journal or "").lower()
    pairs = [
        ("clinical nutrition", ("Clinical Nutrition", "ELSEVIER")),
        ("nutrition reviews", ("Nutrition Reviews", "OXFORD ACADEMIC")),
        ("nutrients", ("Nutrients", "MDPI")),
        ("current nutrition reports", ("Current Nutrition Reports", "SPRINGER")),
        ("european journal of nutrition", ("European Journal of Nutrition", "SPRINGER")),
        ("the lancet", ("THE LANCET", "ELSEVIER")),
        ("frontiers in nutrition", ("FRONTIERS IN NUTRITION", "FRONTIERS")),
        ("journal of clinical medicine", ("JOURNAL OF CLINICAL MEDICINE", "MDPI")),
        ("foods", ("FOODS", "MDPI")),
        ("molecular nutrition", ("MOLECULAR NUTRITION & FOOD RESEARCH", "WILEY")),
        ("antioxidants", ("ANTIOXIDANTS", "MDPI")),
        ("american journal", ("THE AMERICAN JOURNAL OF CLINICAL NUTRITION", "OXFORD ACADEMIC")),
        ("advances in nutrition", ("ADVANCES IN NUTRITION", "ELSEVIER")),
        ("nutrition, metabolism and cardiovascular diseases", ("NUTRITION, METABOLISM AND CARDIOVASCULAR DISEASES", "ELSEVIER")),
        ("sports medicine", ("SPORTS MEDICINE", "SPRINGER")),
        ("scientific reports", ("SCIENTIFIC REPORTS", "NATURE")),
        ("plos", ("PLOS", "PLOS")),
    ]
    for k, v in pairs:
        if k in x:
            return v
    return (journal or "JOURNAL", "")


def render_page(meta: dict, summary: dict, slug: str) -> str:
    title = meta["title"]
    journal = meta.get("journal", "")
    year = meta.get("year", "")
    authors = meta.get("authors", [])
    doi = meta.get("doi", "")
    pmid = meta.get("pmid", "")
    abstract = meta.get("abstract", "")
    brand, publisher = journal_brand(journal)

    def esc(x): return html.escape(x or "")
    mail_subject = urllib.parse.quote("Solicitud de estudio completo — " + title)
    mail_body = urllib.parse.quote(
        "Hola Miguel,\n\nMe gustaría solicitar el estudio completo: " + title + "\n\nMuchas gracias."
    )

    lead = summary.get("lead") or (
        "Esta ficha resume la publicación y sus principales elementos a partir de la información bibliográfica disponible."
    )
    question = summary.get("question") or "La pregunta concreta del estudio se resume a partir de su abstract cuando está disponible."
    methods = summary.get("methods") or "El diseño y la muestra se pueden consultar en la fuente original."
    findings = summary.get("findings") or "Los principales resultados se recogen en el abstract y en la publicación original."
    interpretation = summary.get("interpretation") or "La interpretación debe hacerse atendiendo al diseño, comparador y contexto del estudio."
    limitations = summary.get("limitations") or "El abstract no especifica limitaciones; consulte el artículo completo para una valoración detallada."

    authors_html = ", ".join(esc(a) for a in authors)
    doi_link = (
        f'<a class="meta-link" href="https://doi.org/{urllib.parse.quote(doi, safe="/")}" target="_blank" rel="noopener">DOI</a>'
        if doi else ""
    )
    pmid_link = (
        f'<a class="meta-link" href="https://pubmed.ncbi.nlm.nih.gov/{esc(pmid)}/" target="_blank" rel="noopener">PubMed</a>'
        if pmid else ""
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Miguel López Moreno</title>
<meta name="description" content="{esc(lead[:155])}">
<meta name="author" content="Miguel López Moreno">
<link rel="canonical" href="https://nutreconciencia.com/articulos/{slug}/">
<link rel="stylesheet" href="../../assets/styles.css?v=30">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(lead[:200])}">
<meta property="og:type" content="article">
</head>
<body>
<nav class="nav"><div class="nav-inner">
<a class="brand" href="../../index.html">Miguel López Moreno <span>/ Nutreconciencia</span></a>
<button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false"><span class="open">☰</span><span class="close">×</span></button>
<div class="links">
<a href="../../articulos/index.html">Investigación</a>
<a href="../../prensa/index.html">Prensa</a>
<a href="../../libro/index.html">Libro</a>
<a href="../../sobre-mi/index.html">Sobre mí</a>
<a href="../../podcasts/index.html">Podcasts</a>
</div></div></nav>

<main>
<section class="study-hero">
<div class="inner">
<div class="paper-cover" style="max-width:820px;margin:0 auto">
<div class="paper-cover-head">
<div class="paper-cover-kicker">SCIENTIFIC PAPER</div>
<div class="paper-cover-journal">{esc(brand)}</div>
<div class="paper-cover-publisher">{esc(publisher)}</div>
<div class="paper-cover-issue">{esc(journal)} · {esc(year)}</div>
</div>
<div class="paper-cover-body">
<div class="paper-cover-title">{esc(title)}</div>
<div class="paper-cover-type">Scientific summary ↗</div>
</div></div>
</div>
</section>

<section class="cream"><div class="inner">
<div class="science-glance">
<div class="summary-panel">
<div class="summary-kicker">Resumen científico</div>
<h2>Lo esencial en menos de un minuto.</h2>
<p>{esc(lead)}</p>
</div>
<div class="insight-grid">
<div class="insight-card"><div class="num">01</div><h3>La pregunta</h3><p>{esc(question)}</p></div>
<div class="insight-card"><div class="num">02</div><h3>Qué hicieron</h3><p>{esc(methods)}</p></div>
<div class="insight-card"><div class="num">03</div><h3>Qué encontraron</h3><p>{esc(findings)}</p></div>
</div>
</div>

<div class="study-layout" style="max-width:880px;margin:0 auto">
<article class="study-main article-prose">
<h2>Cómo interpretarlo</h2><p>{esc(interpretation)}</p>
<h2>Limitaciones y contexto</h2><p>{esc(limitations)}</p>
<div class="paper-metadata-row">
<span>{esc(year)}</span><span>{esc(journal)}</span>{doi_link}{pmid_link}
</div>
{"<p class='study-authors'><strong>Autores:</strong> "+authors_html+"</p>" if authors_html else ""}
{"<div class='study-abstract'><h2>Abstract</h2><p>"+esc(abstract)+"</p></div>" if abstract and not summary else ""}
<div class="study-request">
<strong>¿Quieres consultar el estudio completo?</strong>
<a href="mailto:miguel@nutreconciencia.com?subject={mail_subject}&body={mail_body}">Solicitar el estudio completo por email</a>
<small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small>
</div>
</article>
</div>
</div></section>
</main>
<script>
document.querySelectorAll('.mobile-menu-toggle').forEach(btn=>{{btn.addEventListener('click',()=>{{const nav=btn.closest('.nav');const open=nav.classList.toggle('nav-open');btn.setAttribute('aria-expanded',open?'true':'false');}});}});
</script>
</body></html>"""


def normalize_title_key(value: str) -> str:
    """Normalize title text for duplicate matching."""
    value = html.unescape(value or "").lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def load_local_meta(folder: Path) -> dict:
    meta_file = folder / "orcid.json"
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def identity_from_meta(meta: dict) -> dict:
    return {
        "doi": (meta.get("doi") or "").strip().lower(),
        "pmid": str(meta.get("pmid") or "").strip(),
        "orcid_work_id": str(
            meta.get("orcid_work_id")
            or meta.get("put_code")
            or meta.get("orcid_put_code")
            or ""
        ).strip(),
        "title": normalize_title_key(meta.get("title") or ""),
    }


def build_article_index(articles_root: Path) -> dict:
    """Index ORCID-managed pages by DOI, PMID, ORCID work id and normalized title."""
    index = {"doi": {}, "pmid": {}, "orcid_work_id": {}, "title": {}}
    for folder in articles_root.iterdir():
        if not folder.is_dir():
            continue
        meta = load_local_meta(folder)
        if not meta:
            continue
        ident = identity_from_meta(meta)
        for key, value in ident.items():
            if value and value not in index[key]:
                index[key][value] = folder
    return index


def find_existing_folder(index: dict, meta: dict):
    """Reuse an existing canonical folder by the strongest available identifier."""
    ident = identity_from_meta(meta)
    for key in ("doi", "pmid", "orcid_work_id", "title"):
        value = ident[key]
        if value and value in index[key]:
            return index[key][value]
    return None


def safe_unique_slug(title: str, root: Path) -> str:
    """Create a new slug only when no existing publication can be reused."""
    base = slugify(title) or "paper"
    candidate = base
    counter = 2
    while (root / candidate).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate

def main():
    ART.mkdir(exist_ok=True)
    page = 0
    groups = []
    while True:
        url = "https://pub.orcid.org/v3.0/" + ORCID + "/works?" + urllib.parse.urlencode(
            {"page": page, "page-size": 100}
        )
        data = get_json(url, {"Accept": "application/vnd.orcid+json"})
        chunk = data.get("group", [])
        if not chunk:
            break
        groups.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1

    seen = set()
    updated = 0
    for group in groups:
        s = (group.get("work-summary") or [{}])[0]
        title = val(s.get("title", {}).get("title"))
        if not title:
            continue

        ext = s.get("external-ids", {}).get("external-id", [])
        doi = ""
        for e in ext:
            if (e.get("external-id-type") or "").lower() == "doi":
                doi = val(e.get("external-id-value")).strip()
                break

        key = (doi or title).lower()
        if key in seen:
            continue
        seen.add(key)

        year = val((s.get("publication-date") or {}).get("year"))
        journal = val(s.get("journal-title"))
        orcid_work_id = str(
            s.get("put-code")
            or s.get("put_code")
            or s.get("display-index")
            or ""
        ).strip()

        # Never choose a folder from the slug alone. Reuse an existing article
        # by DOI, PMID, ORCID work id or normalized title whenever possible.
        pre_meta = {
            "title": title,
            "year": year,
            "journal": journal,
            "doi": doi,
            "pmid": "",
            "orcid": ORCID,
            "orcid_work_id": orcid_work_id,
        }
        article_index = build_article_index(ART)
        folder = find_existing_folder(article_index, pre_meta)

        if folder is None:
            folder = ART / safe_unique_slug(title, ART)
            folder.mkdir(exist_ok=True)

        # Do not overwrite manually curated pages that do not carry orcid.json.
        orcid_file = folder / "orcid.json"
        existing_page = folder / "index.html"
        if existing_page.exists() and not orcid_file.exists():
            continue

        pmid = pubmed_search(doi, title)
        pm = pubmed_record(pmid)
        cr = crossref_record(doi) if not pm else {}

        meta = {
            "title": title,
            "year": pm.get("year") or year,
            "journal": pm.get("journal") or journal,
            "authors": pm.get("authors") or [],
            "doi": pm.get("doi") or doi or cr.get("doi",""),
            "pmid": pmid,
            "abstract": pm.get("abstract") or cr.get("abstract") or "",
            "orcid": ORCID,
            "orcid_work_id": orcid_work_id,
        }

        summary = openai_summary(meta["title"], meta["abstract"], meta["journal"], meta["year"])

        orcid_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        page_slug = folder.name
        (folder / "index.html").write_text(render_page(meta, summary, page_slug), encoding="utf-8")
        updated += 1
        print("Updated:", folder.name)

    print(f"ORCID sync complete. Updated {updated} article pages. Duplicate-safe identity matching enabled.")


if __name__ == "__main__":
    main()
