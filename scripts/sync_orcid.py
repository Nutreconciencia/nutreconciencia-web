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
    title_node = art.find(".//ArticleTitle")
    title = "".join(title_node.itertext()).strip() if title_node is not None else ""
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
        "publication_types": [
            (node.text or "").strip()
            for node in art.findall(".//PublicationTypeList/PublicationType")
            if (node.text or "").strip()
        ],
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



def translate_to_spanish(text: str) -> str:
    """Translate short scientific text to Spanish without requiring an API key."""
    text = (text or "").strip()
    if not text:
        return ""

    # Avoid translating text that already looks Spanish.
    spanish_markers = [
        " el ", " la ", " los ", " las ", " una ", " un ",
        " fue ", " fueron ", " durante ", " estudio ", " resultados "
    ]
    lower = f" {text.lower()} "
    if sum(marker in lower for marker in spanish_markers) >= 2:
        return text

    chunks = []
    remaining = text

    # Public Google Translate endpoint (no key). Keep chunks small and preserve
    # paragraph boundaries. This is used only for generated summary snippets,
    # not for the article's original title or abstract.
    while remaining:
        chunk = remaining[:1800]
        if len(remaining) > 1800:
            split_at = max(chunk.rfind(". "), chunk.rfind("; "), chunk.rfind(" "))
            if split_at > 500:
                chunk = remaining[:split_at + 1]
        try:
            url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode({
                "client": "gtx",
                "sl": "en",
                "tl": "es",
                "dt": "t",
                "q": chunk,
            })
            data = json.loads(get_text(url))
            translated = "".join(
                item[0] for item in data[0]
                if isinstance(item, list) and item and item[0]
            )
            chunks.append(translated or chunk)
        except Exception as exc:
            print("Translation fallback:", exc)
            chunks.append(chunk)
        remaining = remaining[len(chunk):]

    return " ".join(chunks).strip()



def detect_article_type(meta: dict) -> str:
    types = [str(x).lower() for x in meta.get("publication_types", [])]
    title = str(meta.get("title") or "").lower()

    if any("randomized controlled trial" in x or "clinical trial" in x for x in types):
        return "research"
    if any("meta-analysis" in x or "systematic review" in x or x == "review" for x in types):
        return "review"
    if any("editorial" in x or "comment" in x or "letter" in x or "perspective" in x for x in types):
        return "commentary"
    if any("review" in title for _ in [0]):
        return "review"
    return "research"


def translate_to_spanish(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    # Avoid translating text that already looks Spanish.
    lower = f" {text.lower()} "
    spanish_markers = [
        " el ", " la ", " los ", " las ", " una ", " un ",
        " fue ", " fueron ", " durante ", " estudio ", " resultados ",
        " objetivo ", " evaluó ", " comparó "
    ]
    if sum(marker in lower for marker in spanish_markers) >= 2:
        return text

    chunks = []
    remaining = text
    while remaining:
        chunk = remaining[:1800]
        if len(remaining) > 1800:
            split_at = max(
                chunk.rfind(". "),
                chunk.rfind("; "),
                chunk.rfind(" ")
            )
            if split_at > 500:
                chunk = remaining[:split_at + 1]

        try:
            url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode({
                "client": "gtx",
                "sl": "en",
                "tl": "es",
                "dt": "t",
                "q": chunk,
            })
            data = json.loads(get_text(url))
            translated = "".join(
                item[0]
                for item in data[0]
                if isinstance(item, list) and item and item[0]
            )
            chunks.append(translated or chunk)
        except Exception as exc:
            print("Translation fallback:", exc)
            chunks.append(chunk)

        remaining = remaining[len(chunk):]

    return " ".join(chunks).strip()


def extract_structured_sections(text: str) -> dict:
    labels = {
        "question": ["OBJECTIVES", "OBJECTIVE", "AIMS", "AIM", "PURPOSE", "BACKGROUND AND OBJECTIVES"],
        "methods": ["METHODS", "METHOD", "DESIGN"],
        "findings": ["RESULTS", "FINDINGS", "MAIN RESULTS"],
        "interpretation": ["CONCLUSION", "CONCLUSIONS", "INTERPRETATION", "IMPLICATIONS"],
        "limitations": ["LIMITATIONS", "STRENGTHS AND LIMITATIONS"],
    }

    matches = []
    for field, variants in labels.items():
        for label in variants:
            pattern = re.compile(rf'(?<!\w){re.escape(label)}\s*(?::|-)\s*', flags=re.I)
            m = pattern.search(text)
            if m:
                matches.append((m.start(), m.end(), field))
                break

    matches.sort(key=lambda x: x[0])
    sections = {}
    for i, (start_pos, end_pos, field) in enumerate(matches):
        stop = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        sections[field] = text[end_pos:stop].strip(" ;.-")
    return sections


def scientific_summary_from_abstract(title: str, abstract: str, journal: str, year: str, article_type: str = "research") -> dict:
    """
    Build Spanish summary from abstract, adapting the structure to article type.
    """
    text = clean_abstract(abstract)
    if not text:
        return {}

    sections = extract_structured_sections(text)

    if article_type == "research":
        question_raw = sections.get("question", "")
        if question_raw:
            sentences = re.split(r'(?<=[.!?])\s+', question_raw)
            candidates = [
                s.strip() for s in sentences
                if any(term in s.lower() for term in [
                    "evaluat", "assess", "aim", "determin", "examin",
                    "compar", "investigat", "effect of", "effect on"
                ])
            ]
            if candidates:
                question_raw = " ".join(candidates[:2])

        question = translate_to_spanish(question_raw) if question_raw else (
            "El abstract no presenta un apartado de objetivos explícito; "
            "la pregunta del estudio debe reconstruirse a partir del título y del artículo completo."
        )
        if question_raw and not question.lower().startswith(("el objetivo", "el estudio", "esta investigación")):
            question = "El objetivo fue " + question.rstrip(".") + "."

        methods = translate_to_spanish(sections.get("methods", "")) if sections.get("methods") else (
            "El abstract no presenta un apartado de métodos estructurado; "
            "para describir con precisión el diseño y la muestra es necesario consultar la publicación original."
        )
        findings = translate_to_spanish(sections.get("findings", "")) if sections.get("findings") else (
            "El abstract no presenta un apartado de resultados estructurado; "
            "los resultados concretos deben consultarse en la publicación original."
        )
        interpretation = translate_to_spanish(sections.get("interpretation", "")) if sections.get("interpretation") else (
            "El abstract no presenta una conclusión diferenciada; "
            "la interpretación debe limitarse a los resultados descritos y al diseño del estudio."
        )
        limitations = translate_to_spanish(sections.get("limitations", "")) if sections.get("limitations") else ""

        lead_source = sections.get("findings") or sections.get("question") or ""
        lead = translate_to_spanish(lead_source)
        if lead and len(lead) > 550:
            lead = lead[:547].rsplit(" ", 1)[0] + "..."
        if not lead:
            lead = "Resumen de los principales elementos descritos en el abstract."

        return {
            "mode": "research",
            "lead": lead,
            "question": question[:1000],
            "methods": methods[:1300],
            "findings": findings[:1600],
            "interpretation": interpretation[:1000],
            "limitations": limitations[:1000],
        }

    # Review / perspective / editorial-style paper:
    # Do not pretend it has participants or an intervention when it does not.
    sentences = re.split(r'(?<=[.!?])\s+', text)
    first = " ".join(sentences[:3]).strip()

    if article_type == "review":
        scope = sections.get("question") or first
        synthesis = sections.get("findings") or sections.get("interpretation") or " ".join(sentences[2:6]).strip()
        conclusion = sections.get("interpretation") or (
            sentences[-1] if sentences else ""
        )
        return {
            "mode": "review",
            "lead": translate_to_spanish(synthesis)[:700],
            "question": translate_to_spanish(scope)[:1100],
            "methods": "",
            "findings": translate_to_spanish(synthesis)[:1600],
            "interpretation": translate_to_spanish(conclusion)[:1100],
            "limitations": translate_to_spanish(sections.get("limitations", ""))[:1000],
        }

    # Commentary / perspective / editorial / unstructured narrative:
    scope = first
    synthesis = " ".join(sentences[3:7]).strip() or first
    conclusion = sections.get("interpretation") or (sentences[-1] if sentences else "")
    return {
        "mode": "commentary",
        "lead": translate_to_spanish(scope)[:700],
        "question": translate_to_spanish(scope)[:1100],
        "methods": "",
        "findings": translate_to_spanish(synthesis)[:1600],
        "interpretation": translate_to_spanish(conclusion)[:1100],
        "limitations": translate_to_spanish(sections.get("limitations", ""))[:1000],
    }


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
        "El objetivo del estudio no pudo reconstruirse con suficiente detalle a partir de los datos disponibles."
    )
    methods = summary.get("methods") or (
        "El abstract disponible no aporta suficiente información para describir con precisión el diseño y la muestra."
    )
    findings = summary.get("findings") or (
        "El abstract disponible no aporta suficiente información para resumir los resultados con precisión."
    )
    interpretation = summary.get("interpretation") or (
        "La interpretación debe limitarse a lo que permiten sostener el diseño y los resultados descritos en el abstract."
    )
    article_mode = summary.get("mode") or detect_article_type(meta)
    limitations = summary.get("limitations", "").strip()

    authors_html = ", ".join(esc(a) for a in authors)

    doi_link = (
        f'<a class="clean-action" href="https://doi.org/{urllib.parse.quote(doi, safe="/")}" target="_blank" rel="noopener">Ver DOI ↗</a>'
        if doi else ""
    )
    pmid_link = (
        f'<a class="clean-action clean-action-dark" href="https://pubmed.ncbi.nlm.nih.gov/{esc(pmid)}/" target="_blank" rel="noopener">Ver en PubMed ↗</a>'
        if pmid else ""
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
<link rel="stylesheet" href="../../assets/styles.css?v=42">
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
      <div class="clean-kicker">{f"LA PREGUNTA" if article_mode == "research" else "QUÉ ABORDA"}</div>
      <h2>{f"¿Qué quiso estudiar?" if article_mode == "research" else "¿Qué cuestión aborda?"}</h2>
      <p>{esc(question)}</p>
    </div>

    {f"""<div class="clean-section">
      <div class="clean-kicker">Qué hicieron</div>
      <h2>Diseño del estudio</h2>
      <p>{esc(methods)}</p>
    </div>""" if article_mode == "research" and methods else ""}

    <div class="clean-section">
      <div class="clean-kicker">{f"QUÉ ENCONTRARON" if article_mode == "research" else "QUÉ APORTA"}</div>
      <h2>{f"Principales resultados" if article_mode == "research" else "Qué aporta el artículo"}</h2>
      <p>{esc(findings)}</p>
    </div>

    <div class="clean-section">
      <div class="clean-kicker">INTERPRETACIÓN</div>
      <h2>{f"Cómo interpretarlo" if article_mode == "research" else "Qué significa"}</h2>
      <p>{esc(interpretation)}</p>
    </div>

    {f"""<div class="clean-section">
      <div class="clean-kicker">Contexto</div>
      <h2>Limitaciones y contexto</h2>
      <p>{esc(limitations)}</p>
    </div>""" if limitations else ""}

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
    Synchronize /articulos/index.html without relying on a brittle closing marker.

    - Locates the paper grid from <div class="journal-grid" id="paperGrid"> to the
      next closing </div></section></main> sequence.
    - Deduplicates cards by href and normalized title.
    - Ignores redirect/noindex article folders.
    - Adds missing canonical ORCID cards.
    """
    index_file = ART / "index.html"
    if not index_file.exists():
        print("Research index not found; skipping index synchronization.")
        return

    page = index_file.read_text(encoding="utf-8")

    grid_marker = '<div class="journal-grid" id="paperGrid">'
    start = page.find(grid_marker)
    if start == -1:
        print("Research grid marker not found; skipping index synchronization.")
        return

    grid_start = start + len(grid_marker)

    # Find the end of the grid using the actual static structure, while allowing
    # whitespace/newlines between the closing div/section/main tags.
    close_re = re.compile(r'</div>\s*</div>\s*</section>\s*</main>', re.S)
    close_match = close_re.search(page, grid_start)
    if not close_match:
        print("Research grid closing structure not found; skipping index synchronization.")
        return

    grid_inner = page[grid_start:close_match.start()]

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
    updated_page = (
        page[:grid_start]
        + new_grid
        + page[close_match.start():]
    )

    if updated_page != page:
        index_file.write_text(updated_page, encoding="utf-8")

    print(
        f"Research index synchronized: removed {removed} duplicate cards; "
        f"added {added} missing publication cards; "
        f"total cards kept {len(unique_cards)}."
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

        existing_meta = load_local_meta(folder)

        # Query PubMed and Crossref independently. Crossref is useful as a
        # fallback even when PubMed returned a partial record.
        pmid = pubmed_search(doi, title) or str(existing_meta.get("pmid") or "")
        pm = pubmed_record(pmid)
        cr = crossref_record(doi) if doi else {}

        abstract = (
            pm.get("abstract")
            or cr.get("abstract")
            or existing_meta.get("abstract")
            or ""
        )

        authors = (
            pm.get("authors")
            or cr.get("authors")
            or existing_meta.get("authors")
            or []
        )

        meta = {
            "title": pm.get("title") or cr.get("title") or title or existing_meta.get("title") or "",
            "year": pm.get("year") or cr.get("year") or year or existing_meta.get("year") or "",
            "journal": pm.get("journal") or cr.get("journal") or journal or existing_meta.get("journal") or "",
            "authors": authors,
            "doi": pm.get("doi") or cr.get("doi") or doi or existing_meta.get("doi") or "",
            "pmid": pmid,
            "abstract": clean_abstract(abstract),
            "publication_types": pm.get("publication_types") or existing_meta.get("publication_types") or [],
            "orcid": ORCID,
            "orcid_work_id": orcid_work_id or existing_meta.get("orcid_work_id") or "",
        }

        print(
            f"Metadata for {folder.name}: PMID={meta['pmid'] or '-'}; "
            f"DOI={meta['doi'] or '-'}; abstract_chars={len(meta['abstract'])}"
        )
        print("Scientific summary: generated locally from abstract; no OpenAI API required.")

        article_type = detect_article_type(meta)
        summary = scientific_summary_from_abstract(
            meta["title"],
            meta["abstract"],
            meta["journal"],
            meta["year"],
            article_type,
        )
        summary["article_type"] = article_type

        orcid_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        page_slug = folder.name
        (folder / "index.html").write_text(render_page(meta, summary, page_slug), encoding="utf-8")
        updated += 1
        print("Updated:", folder.name)

    update_research_index()
    print(f"ORCID sync complete. Updated {updated} article pages. Duplicate-safe identity matching enabled.")


if __name__ == "__main__":
    main()
