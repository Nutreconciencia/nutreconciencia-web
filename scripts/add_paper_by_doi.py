#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys, urllib.parse, urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'articulos'
BASE = 'https://nutreconciencia.com'
PERSON = BASE + '/#person'
UA = 'NutreconcienciaWeb/1.0 (https://nutreconciencia.com/)'

def clean(v: str) -> str:
    return re.sub(r'\s+', ' ', v or '').strip()

def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))

def crossref(doi: str) -> dict:
    u = 'https://api.crossref.org/works/' + urllib.parse.quote(doi, safe='')
    return get_json(u)['message']

def pubmed_id(doi: str) -> str:
    term = urllib.parse.quote(f'{doi}[DOI]', safe='')
    u = ('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
         f'?db=pubmed&term={term}&retmode=json&tool=nutreconciencia_web&email=miguel@nutreconciencia.com')
    try:
        ids = get_json(u).get('esearchresult', {}).get('idlist', [])
        return ids[0] if ids else ''
    except Exception:
        return ''

def year_of(item: dict) -> str:
    for key in ('published-print','published-online','issued','created'):
        parts = item.get(key, {}).get('date-parts', [])
        if parts and parts[0]: return str(parts[0][0])
    return ''

def authors_of(item: dict) -> list[str]:
    out=[]
    for a in item.get('author', []):
        n=clean(f"{a.get('given','')} {a.get('family','')}")
        if n: out.append(n)
    return out

def slugify(s: str) -> str:
    trans = str.maketrans('áéíóúüñ','aeiouun')
    s=clean(s).lower().translate(trans)
    return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',s)).strip('-')[:120].rstrip('-')

def build_page(item, slug, doi, pmid):
    title=clean((item.get('title') or [''])[0])
    journal=clean((item.get('container-title') or [''])[0]) or 'Scientific publication'
    year=year_of(item)
    authors=', '.join(authors_of(item))
    canonical=f'{BASE}/articulos/{slug}/'
    summary=f'Publicación científica en {journal}' + (f' ({year})' if year else '') + '. Esta ficha reúne sus datos bibliográficos y enlaces a la fuente original.'
    schema={
      '@context':'https://schema.org','@type':'ScholarlyArticle',
      '@id':canonical.rstrip('/')+'/#article','url':canonical,'headline':title,
      'author':[{'@type':'Person','@id':PERSON,'name':'Miguel López Moreno'}],
      'sameAs':[f'https://doi.org/{doi}'] + ([f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'] if pmid else []),
      'isPartOf':{'@type':'Periodical','name':journal}
    }
    if year: schema['datePublished']=year
    pubmed_btn=(f'<a class="btn primary" href="https://pubmed.ncbi.nlm.nih.gov/{escape(pmid)}/" target="_blank" rel="noopener">Ver en PubMed ↗</a>' if pmid else '')
    pill_pub='<span class="pill">PubMed</span>' if pmid else ''
    mail='mailto:miguel@nutreconciencia.com?subject='+urllib.parse.quote(f'Solicitud de estudio completo — {title}')+'&body='+urllib.parse.quote(f'Hola Miguel,\n\nMe gustaría solicitar el estudio completo: {title}\n\nMuchas gracias.')
    return f'''<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | Miguel López Moreno</title>
<meta name="description" content="{escape(summary)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{escape(title)} | Miguel López Moreno"><meta property="og:description" content="{escape(summary)}"><meta property="og:type" content="article"><meta property="og:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
<link rel="stylesheet" href="../../assets/styles.css?v=27">
<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>
<meta property="og:url" content="{canonical}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{escape(title)} | Miguel López Moreno"><meta name="twitter:description" content="{escape(summary)}"><meta name="twitter:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
</head><body>
<nav class="nav"><div class="nav-inner"><a class="brand" href="/">Miguel López Moreno <span>/ Nutreconciencia</span></a><button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false"><span class="open">☰</span><span class="close">×</span></button><div class="links"><a href="/articulos/">Investigación</a><a href="/articulos/">Artículos</a><a href="/prensa/">Prensa</a><a href="/libro/">Libro</a><a href="/sobre-mi/">Sobre mí</a><a href="/podcasts/">Podcasts</a></div></div></nav>
<div class="breadcrumbs"><a href="/articulos/">Artículos</a> → {escape(title)}</div>
<main class="article-shell"><section class="study-hero article-top"><div class="article-kicker">Resumen científico · {escape(journal)} · {escape(year)}</div><h1 class="study-title-original">{escape(title)}</h1><div class="article-original"><strong>Título original:</strong> {escape(title)}</div><div class="article-meta"><span class="pill">{escape(journal)}</span><span class="pill">{escape(year)}</span><span class="pill">DOI</span>{pill_pub}</div></section>
<section class="study-layout article-layout"><div id="resumen" class="study-main article-prose"><p class="summary-lead">{escape(summary)}</p><div class="article-note">Este resumen reúne únicamente información bibliográfica y no sustituye al artículo científico original.</div><h2 id="publicacion">Publicación original</h2><p><strong>{escape(title)}</strong></p><p>{escape(authors)}</p><div class="source-buttons"><a class="btn soft" href="https://doi.org/{escape(doi)}" target="_blank" rel="noopener">Ver DOI ↗</a>{pubmed_btn}</div></div><aside class="study-side article-sidebar"><div class="sidebar-card"><strong>En esta página</strong><div class="sidebar-links"><a href="#resumen">Resumen</a><a href="#publicacion">Publicación</a></div></div><div class="sidebar-card"><strong>Artículo original</strong><div><strong>Título</strong><br>{escape(title)}</div></div></aside></section>
<div class="study-request"><strong>¿Quieres consultar el estudio completo?</strong><a href="{mail}">Solicitar el estudio completo por email</a><small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small></div></main>
<footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div><div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br><a href="mailto:miguel@nutreconciencia.com">miguel@nutreconciencia.com</a><br>© 2026 Miguel López Moreno.</div></div></footer>
<script>document.querySelectorAll('.mobile-menu-toggle').forEach(btn=>{{btn.addEventListener('click',()=>{{const nav=btn.closest('.nav');const open=nav.classList.toggle('nav-open');btn.setAttribute('aria-expanded',open?'true':'false');}});}});</script>
</body></html>'''

def main():
    if len(sys.argv)!=2: raise SystemExit('Uso: python add_paper_by_doi.py DOI')
    doi=clean(sys.argv[1]).replace('https://doi.org/','').strip('/')
    item=crossref(doi); title=clean((item.get('title') or [''])[0])
    if not title: raise RuntimeError('Crossref no devolvió título')
    slug=slugify(title); folder=ART/slug
    if folder.exists(): raise RuntimeError(f'La carpeta ya existe: {folder}')
    pmid=pubmed_id(doi); folder.mkdir(parents=True)
    (folder/'index.html').write_text(build_page(item,slug,doi,pmid),encoding='utf-8')
    (folder/'metadata.json').write_text(json.dumps({'doi':doi,'title':title,'authors':authors_of(item),'journal':clean((item.get('container-title') or [''])[0]),'publisher':clean(item.get('publisher','')),'year':year_of(item),'pmid':pmid},ensure_ascii=False,indent=2),encoding='utf-8')
    print('NEW PAPER CREATED — EDITORIAL TEMPLATE'); print('DOI:',doi); print('Title:',title); print('Slug:',slug); print('PMID:',pmid or 'not found')

if __name__=='__main__': main()

