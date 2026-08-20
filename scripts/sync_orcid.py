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

    def esc(x):
        return html.escape(x or "")

    mail_subject = urllib.parse.quote("Solicitud de estudio completo — " + title)
    mail_body = urllib.parse.quote(
        "Hola Miguel,\n\nMe gustaría solicitar el estudio completo: " + title + "\n\nMuchas gracias."
    )

    lead = summary.get("lead") or (
        "Esta ficha resume la publicación y sus principales elementos a partir de la información bibliográfica disponible."
    )
    question = summary.get("question") or (
        "La pregunta concreta del estudio se resume a partir del abstract cuando está disponible."
    )
    methods = summary.get("methods") or (
        "El diseño y la muestra se pueden consultar en la fuente original."
    )
    findings = summary.get("findings") or (
        "Los principales resultados se recogen en el abstract y en la publicación original."
    )
    interpretation = summary.get("interpretation") or (
        "La interpretación debe hacerse atendiendo al diseño, comparador y contexto del estudio."
    )
    limitations = summary.get("limitations") or (
        "El abstract no especifica limitaciones; consulte el artículo completo para una valoración detallada."
    )

    authors_html = ", ".join(esc(a) for a in authors)

    doi_link = (
        f'<a class="clean-action" href="https://doi.org/{urllib.parse.quote(doi, safe="/")}" target="_blank" rel="noopener">Ver DOI ↗</a>'
        if doi else ""
    )
    pmid_link = (
        f'<a class="clean-action clean-action-dark" href="https://pubmed.ncbi.nlm.nih.gov/{esc(pmid)}/" target="_blank" rel="noopener">Ver en PubMed ↗</a>'
        if pmid else ""
    )

    abstract_block = (
        f'<div class="clean-section"><div class="clean-kicker">Abstract</div>'
        f'<p>{esc(abstract)}</p></div>'
        if abstract else ""
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | Miguel López Moreno</title>
<meta name="description" content="{esc(lead[:155])}">
<meta name="author" content="Miguel López Moreno">
<link rel="canonical" href="https://nutreconciencia.com/articulos/{esc(slug)}/">
<link rel="stylesheet" href="../../assets/styles.css?v=36">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(lead[:200])}">
<meta property="og:type" content="article">

<style>
.clean-paper {{
  max-width: 980px;
  margin: 0 auto;
  padding: 70px 28px 96px;
}}
.clean-paper section,
.clean-paper article,
.clean-paper div.clean-section,
.clean-paper .clean-summary,
.clean-paper .clean-request {{
  min-height: 0 !important;
  height: auto !important;
}}
.clean-header {{
  max-width: 860px;
  margin: 0 auto 58px;
}}
.clean-journal {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(1.65rem, 3.1vw, 2.65rem);
  line-height: 1.05;
  letter-spacing: -0.02em;
  margin: 0 0 7px;
}}
.clean-publisher {{
  font-size: .76rem;
  letter-spacing: .14em;
  text-transform: uppercase;
  opacity: .65;
  margin-bottom: 24px;
}}
.clean-meta {{
  display:flex;
  flex-wrap:wrap;
  gap:10px 16px;
  font-size:.78rem;
  letter-spacing:.06em;
  text-transform:uppercase;
  opacity:.68;
  margin-bottom:18px;
}}
.clean-title {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(2rem, 4.3vw, 3.8rem);
  line-height: 1.06;
  letter-spacing: -.025em;
  margin: 0 0 20px;
  font-weight: 500;
}}
.clean-authors {{
  font-size: .98rem;
  line-height: 1.65;
  opacity: .72;
  margin: 0;
}}
.clean-lead {{
  max-width: 760px;
  font-size: 1.18rem;
  line-height: 1.65;
  margin: 0 0 44px;
}}
.clean-divider {{
  height:1px;
  background:rgba(35,35,31,.14);
  margin: 0 0 44px;
}}
.clean-section {{
  max-width: 760px;
  margin: 0 auto 38px !important;
  padding: 0 !important;
  min-height: 0 !important;
  height: auto !important;
  display: block !important;
  align-items: initial !important;
  justify-content: initial !important;
  place-items: initial !important;
}}
.clean-section:last-child {{
  margin-bottom: 0 !important;
}}
.clean-kicker {{
  font-size:.72rem;
  letter-spacing:.16em;
  text-transform:uppercase;
  font-weight:700;
  color:#596542;
  margin-bottom:12px;
}}
.clean-section h2 {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(1.7rem, 3vw, 2.25rem);
  line-height:1.12;
  font-weight:500;
  margin:0 0 11px;
}}
.clean-section p {{
  font-size:1.04rem;
  line-height:1.72;
  margin:0;
  color:rgba(35,35,31,.82);
}}
.clean-summary {{
  max-width:760px;
  margin: 0 auto 50px;
  padding: 28px 30px;
  border:1px solid rgba(35,35,31,.12);
  border-radius:18px;
  background:rgba(255,255,255,.38);
}}
.clean-summary h2 {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(1.8rem,3.2vw,2.4rem);
  line-height:1.12;
  font-weight:500;
  margin:0 0 12px;
}}
.clean-summary p {{
  font-size:1.03rem;
  line-height:1.67;
  margin:0;
  color:rgba(35,35,31,.82);
}}
.clean-links {{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin-top: 22px;
}}
.clean-action {{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-height:44px;
  padding:10px 17px;
  border:1px solid rgba(35,35,31,.18);
  border-radius:999px;
  text-decoration:none;
  color:inherit;
  background:transparent;
  font-weight:600;
  font-size:.92rem;
}}
.clean-action-dark {{
  background:#22221f;
  color:#fff;
  border-color:#22221f;
}}
.clean-request {{
  max-width:760px;
  margin: 48px auto 0;
  padding: 24px 26px;
  border-left: 2px solid #596542;
  background:rgba(255,255,255,.3);
}}
.clean-request strong {{
  display:block;
  font-size:.8rem;
  letter-spacing:.14em;
  text-transform:uppercase;
  color:#596542;
  margin-bottom:9px;
}}
.clean-request a {{
  font-weight:700;
  text-decoration:underline;
  text-underline-offset:3px;
}}
.clean-request small {{
  display:block;
  margin-top:7px;
  opacity:.62;
}}
@media (max-width: 700px) {{
  .clean-paper {{ padding: 42px 18px 64px; }}
  .clean-header {{ margin-bottom: 40px; }}
  .clean-title {{ font-size: clamp(1.8rem, 10vw, 2.8rem); }}
  .clean-lead {{ font-size:1.02rem; }}
  .clean-summary {{ padding:22px 20px; border-radius:15px; }}
  .clean-section {{ margin-bottom:34px; }}
  .clean-section p {{ font-size:.98rem; }}
  .clean-journal {{ font-size:2rem; }}
}}
</style>
</head>

<body>
<nav class="nav"><div class="nav-inner">
<a class="brand" href="../../index.html">Miguel López Moreno <span>/ Nutreconciencia</span></a>
<button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false">
<span class="open">☰</span><span class="close">×</span>
</button>
<div class="links">
<a href="../../articulos/index.html">Investigación</a>
<a href="../../prensa/index.html">Prensa</a>
<a href="../../libro/index.html">Libro</a>
<a href="../../sobre-mi/index.html">Sobre mí</a>
<a href="../../podcasts/index.html">Podcasts</a>
</div></div></nav>

<main>
<section class="cream">
  <div class="clean-paper">
    <header class="clean-header">
      <div class="clean-meta">
        <span>Scientific paper</span>
        <span>{esc(year)}</span>
      </div>
      <div class="clean-journal">{esc(brand)}</div>
      <div class="clean-publisher">{esc(publisher)}</div>
      <h1 class="clean-title">{esc(title)}</h1>
      {f'<p class="clean-authors">{authors_html}</p>' if authors_html else ''}
    </header>

    <div class="clean-summary">
      <div class="clean-kicker">Resumen científico</div>
      <h2>Lo esencial en menos de un minuto.</h2>
      <p>{esc(lead)}</p>
    </div>

    <div class="clean-divider"></div>

    <div class="clean-section">
      <div class="clean-kicker">La pregunta</div>
      <h2>¿Qué quiso estudiar?</h2>
      <p>{esc(question)}</p>
    </div>

    <div class="clean-section">
      <div class="clean-kicker">Qué hicieron</div>
      <h2>Diseño del estudio</h2>
      <p>{esc(methods)}</p>
    </div>

    <div class="clean-section">
      <div class="clean-kicker">Qué encontraron</div>
      <h2>Principales resultados</h2>
      <p>{esc(findings)}</p>
    </div>

    <div class="clean-section">
      <div class="clean-kicker">Interpretación</div>
      <h2>Cómo interpretarlo</h2>
      <p>{esc(interpretation)}</p>
    </div>

    <div class="clean-section">
      <div class="clean-kicker">Contexto</div>
      <h2>Limitaciones y contexto</h2>
      <p>{esc(limitations)}</p>
      {abstract_block}
    </div>

    <div class="clean-section">
      <div class="clean-kicker">Publicación original</div>
      <h2>{esc(journal)} · {esc(year)}</h2>
      <div class="clean-links">{doi_link}{pmid_link}</div>
    </div>

    <div class="clean-request">
      <strong>¿Quieres consultar el estudio completo?</strong>
      <a href="mailto:miguel@nutreconciencia.com?subject={mail_subject}&body={mail_body}">Solicitar el estudio completo por email</a>
      <small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small>
    </div>
  </div>
</div>
</main>

<script>
document.querySelectorAll('.mobile-menu-toggle').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const nav = btn.closest('.nav');
    const open = nav.classList.toggle('nav-open');
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }});
}});
</script>
</body>
</html>"""

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


def render_index_card(meta: dict, slug: str) -> str:
    """Render one research card using the same visual classes as /articulos/index.html."""
    title = html.escape(meta.get("title") or "")
    title_key = normalize_title_key(meta.get("title") or "")
    journal = meta.get("journal") or "JOURNAL"
    year = str(meta.get("year") or "")
    brand, publisher = journal_brand(journal)

    return f"""<a class="paper-cover" data-year="{html.escape(year)}" data-title="{html.escape(title_key)}" href="{html.escape(slug)}/index.html">
  <div class="paper-cover-head">
    <div class="paper-cover-kicker">SCIENTIFIC PAPER</div>
    <div class="paper-cover-journal">{html.escape(brand)}</div>
    <div class="paper-cover-publisher">{html.escape(publisher)}</div>
    <div class="paper-cover-issue">{html.escape(journal)} · {html.escape(year)}</div>
  </div>
  <div class="paper-cover-body">
    <div class="paper-cover-title">{title}</div>
    <div class="paper-cover-type">Open the scientific summary ↗</div>
  </div>
</a>"""


def update_research_index() -> None:
    """
    Keep /articulos/index.html synchronized with canonical ORCID publications.

    Existing paper-cover cards are deduplicated by exact href and normalized
    title. Redirect/noindex folders are ignored. Missing canonical ORCID cards
    are appended once.
    """
    index_file = ART / "index.html"
    if not index_file.exists():
        print("Research index not found; skipping index synchronization.")
        return

    page = index_file.read_text(encoding="utf-8")
    grid_marker = '<div class="journal-grid" id="paperGrid">'
    close_marker = '</div></div></div></main>'

    start = page.find(grid_marker)
    if start == -1:
        print("Research grid marker not found; skipping index synchronization.")
        return

    end = page.find(close_marker, start)
    if end == -1:
        print("Research grid closing marker not found; skipping index synchronization.")
        return

    grid_start = start + len(grid_marker)
    grid_inner = page[grid_start:end]

    card_pattern = re.compile(r'<a class="paper-cover"(?P<attrs>.*?)</a>', re.S)
    cards = card_pattern.findall(grid_inner)

    unique_cards = []
    seen_hrefs = set()
    seen_titles = set()
    removed = 0

    for attrs in cards:
        href_match = re.search(r'href="([^"]+)"', attrs)
        title_match = re.search(r'data-title="([^"]*)"', attrs)
        href = href_match.group(1) if href_match else ""
        title_key = normalize_title_key(title_match.group(1) if title_match else "")

        if (href and href in seen_hrefs) or (title_key and title_key in seen_titles):
            removed += 1
            continue

        if href:
            seen_hrefs.add(href)
        if title_key:
            seen_titles.add(title_key)

        unique_cards.append(f'<a class="paper-cover"{attrs}</a>')

    candidates = []
    for folder in sorted(ART.iterdir()):
        if not folder.is_dir():
            continue

        meta = load_local_meta(folder)
        if not meta:
            continue

        page_file = folder / "index.html"
        if not page_file.exists():
            continue

        try:
            page_html = page_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            page_html = ""

        if 'name="robots" content="noindex,follow"' in page_html:
            continue

        slug = folder.name
        href = f"{slug}/index.html"
        title_key = normalize_title_key(meta.get("title") or "")

        if href in seen_hrefs or (title_key and title_key in seen_titles):
            continue

        candidates.append((
            str(meta.get("year") or ""),
            (meta.get("title") or "").lower(),
            render_index_card(meta, slug),
            href,
            title_key,
        ))

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    added = 0
    for _, _, card, href, title_key in candidates:
        if href in seen_hrefs or (title_key and title_key in seen_titles):
            continue
        unique_cards.append(card)
        seen_hrefs.add(href)
        if title_key:
            seen_titles.add(title_key)
        added += 1

    new_grid = "\n" + "\n".join(unique_cards) + "\n"
    updated_page = page[:grid_start] + new_grid + page[end:]

    if updated_page != page:
        index_file.write_text(updated_page, encoding="utf-8")

    print(
        f"Research index synchronized: removed {removed} duplicate cards; "
        f"added {added} missing publication cards; total cards kept {len(unique_cards)}."
    )

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

    update_research_index()
    print(f"ORCID sync complete. Updated {updated} article pages. Duplicate-safe identity matching enabled.")


if __name__ == "__main__":
    main()
