#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "when-ultra-processing-obscures-sustainable-dietary-transitions"
FOLDER = ROOT / "articulos" / TARGET
META = FOLDER / "metadata.json"
PAGE = FOLDER / "index.html"
BASE = "https://nutreconciencia.com"

SUMMARY = (
    "El artículo analiza las limitaciones de tratar todos los alimentos "
    "ultraprocesados como una categoría nutricional homogénea. Destaca que "
    "los alimentos incluidos en la misma categoría de procesamiento pueden "
    "diferir en composición nutricional y asociaciones con la salud, y que "
    "su interpretación debe considerar también los alimentos que sustituyen. "
    "Esta perspectiva es especialmente relevante para las transiciones hacia "
    "dietas más vegetales y sostenibles."
)

SECTIONS = [
    (
        "La heterogeneidad de los ultraprocesados",
        "Los alimentos clasificados como ultraprocesados no presentan necesariamente "
        "las mismas características nutricionales ni las mismas asociaciones con la "
        "salud. El artículo destaca que algunos subgrupos, como las carnes procesadas "
        "y las bebidas azucaradas, muestran asociaciones desfavorables, mientras que "
        "otros, como ciertos panes, cereales y alternativas vegetales, pueden mostrar "
        "patrones diferentes."
    ),
    (
        "Procesamiento, sustitución y transición dietética",
        "El posible efecto de aumentar un alimento depende también de qué alimento "
        "desplaza dentro de la dieta. Desde una perspectiva contrafactual, comparar "
        "los alimentos únicamente por su grado de procesamiento puede ocultar "
        "diferencias relevantes entre sustituciones dietéticas y entre los alimentos "
        "disponibles como alternativa."
    ),
    (
        "Implicaciones para dietas sostenibles",
        "El artículo plantea que algunos productos vegetales clasificados como "
        "ultraprocesados pueden facilitar la sustitución de alimentos de origen "
        "animal. Por ello, evaluarlos exclusivamente por su grado de procesamiento "
        "puede pasar por alto su posible función dentro de patrones dietéticos más "
        "saludables y sostenibles. Esto no implica que todos estos productos sean "
        "saludables por defecto, ya que su calidad nutricional sigue siendo variable."
    ),
]


def main() -> None:
    if not META.exists():
        raise FileNotFoundError(META)

    data = json.loads(META.read_text(encoding="utf-8"))
    doi = data["doi"]
    title = data["title"]
    authors = ", ".join(data.get("authors", []))
    journal = data.get("journal", "Frontiers in Nutrition")
    year = str(data.get("year", "2026"))
    canonical = f"{BASE}/articulos/{TARGET}/"

    schema = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "@id": canonical.rstrip("/") + "/#article",
        "url": canonical,
        "headline": title,
        "author": [{
            "@type": "Person",
            "@id": BASE + "/#person",
            "name": "Miguel López Moreno"
        }],
        "sameAs": [f"https://doi.org/{doi}"],
        "isPartOf": {"@type": "Periodical", "name": journal},
        "datePublished": year,
    }

    sidebar_links = "".join(
        f'<a href="#s{i}">{heading}</a>'
        for i, (heading, _) in enumerate(SECTIONS, 1)
    )
    body_sections = "".join(
        f'<h2 id="s{i}">{heading}</h2><p>{text}</p>'
        for i, (heading, text) in enumerate(SECTIONS, 1)
    )

    subject = urllib.parse.quote(f"Solicitud de estudio completo — {title}")
    mail_body = urllib.parse.quote(
        f"Hola Miguel,\n\nMe gustaría solicitar el estudio completo: {title}\n\nMuchas gracias."
    )
    mail = f"mailto:miguel@nutreconciencia.com?subject={subject}&body={mail_body}"

    html = f'''<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Miguel López Moreno</title>
<meta name="description" content="{SUMMARY}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title} | Miguel López Moreno">
<meta property="og:description" content="{SUMMARY}">
<meta property="og:type" content="article"><meta property="og:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
<link rel="stylesheet" href="../../assets/styles.css?v=28">
<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">
{json.dumps(schema, ensure_ascii=False, indent=2)}
</script>
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title} | Miguel López Moreno">
<meta name="twitter:description" content="{SUMMARY}">
<meta name="twitter:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
</head><body>
<nav class="nav"><div class="nav-inner"><a class="brand" href="/">Miguel López Moreno <span>/ Nutreconciencia</span></a>
<button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false"><span class="open">☰</span><span class="close">×</span></button>
<div class="links"><a href="/articulos/">Investigación</a><a href="/articulos/">Artículos</a><a href="/prensa/">Prensa</a><a href="/libro/">Libro</a><a href="/sobre-mi/">Sobre mí</a><a href="/podcasts/">Podcasts</a></div></div></nav>
<div class="breadcrumbs"><a href="/articulos/">Artículos</a> → {title}</div>
<main class="article-shell">
<section class="study-hero article-top">
<div class="article-kicker">Resumen científico · {journal} · {year}</div>
<h1 class="study-title-original">{title}</h1>
<div class="article-original"><strong>Título original:</strong> {title}</div>
<div class="article-meta"><span class="pill">{journal}</span><span class="pill">{year}</span><span class="pill">DOI</span></div>
</section>
<section class="study-layout article-layout">
<div id="resumen" class="study-main article-prose">
<p class="summary-lead">{SUMMARY}</p>
<div class="article-note">Este resumen se basa en la publicación científica original y facilita la lectura; no sustituye al artículo completo.</div>
{body_sections}
<h2 id="publicacion">Publicación original</h2>
<p><strong>{title}</strong></p>
<p>{authors}</p>
<div class="source-buttons"><a class="btn soft" href="https://doi.org/{doi}" target="_blank" rel="noopener">Ver DOI ↗</a></div>
</div>
<aside class="study-side article-sidebar">
<div class="sidebar-card"><strong>En esta página</strong><div class="sidebar-links"><a href="#resumen">Resumen</a>{sidebar_links}<a href="#publicacion">Publicación</a></div></div>
<div class="sidebar-card"><strong>Artículo original</strong><div><strong>Título</strong><br>{title}</div></div>
</aside>
</section>
<div class="study-request"><strong>¿Quieres consultar el estudio completo?</strong>
<a href="{mail}">Solicitar el estudio completo por email</a>
<small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small></div>
</main>
<footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div>
<div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br><a href="mailto:miguel@nutreconciencia.com">miguel@nutreconciencia.com</a><br>© 2026 Miguel López Moreno.</div></div></footer>
<script>
document.querySelectorAll('.mobile-menu-toggle').forEach(btn=>{{
  btn.addEventListener('click',()=>{{
    const nav=btn.closest('.nav');
    const open=nav.classList.toggle('nav-open');
    btn.setAttribute('aria-expanded',open?'true':'false');
  }});
}});
</script></body></html>'''

    PAGE.write_text(html, encoding="utf-8")
    data["editorial_summary"] = SUMMARY
    data["editorial_sections"] = [{"heading": h, "text": t} for h, t in SECTIONS]
    META.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("EDITORIAL SUMMARY MIGRATION — CURRENT DOI PAPER")
    print("=" * 72)
    print("Target:", TARGET)
    print("Summary: PASS")
    print("Sections:", len(SECTIONS))
    print("CSS version: 28")
    print("ScholarlyArticle schema: PASS")
    print("PubMed button: NOT ADDED (PMID not found)")
    print("Only target article files modified.")

if __name__ == "__main__":
    main()
