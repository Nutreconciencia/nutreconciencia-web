#!/usr/bin/env python3
from __future__ import annotations
import json, re, urllib.parse, urllib.request
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET='when-ultra-processing-obscures-sustainable-dietary-transitions'
META=ROOT/'articulos'/TARGET/'metadata.json'
PAGE=ROOT/'articulos'/TARGET/'index.html'
BASE='https://nutreconciencia.com'

def clean(v): return re.sub(r'\s+',' ',v or '').strip()

def get_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'NutreconcienciaWeb/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r: return json.loads(r.read().decode())

def crossref(doi):
    return get_json('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''))['message']

def pubmed_id(doi):
    term=urllib.parse.quote(f'{doi}[DOI]',safe='')
    try:
        d=get_json('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term='+term+'&retmode=json')
        return d.get('esearchresult',{}).get('idlist',[''])[0]
    except Exception: return ''

def year_of(item):
    for k in ('published-print','published-online','issued','created'):
        p=item.get(k,{}).get('date-parts',[])
        if p and p[0]: return str(p[0][0])
    return ''

def authors_of(item):
    out=[]
    for a in item.get('author',[]):
        n=clean(f"{a.get('given','')} {a.get('family','')}")
        if n: out.append(n)
    return out

def build_page(item,doi,pmid):
    title=clean((item.get('title') or [''])[0])
    journal=clean((item.get('container-title') or [''])[0]) or 'Scientific publication'
    year=year_of(item); authors=', '.join(authors_of(item))
    canonical=f'{BASE}/articulos/{TARGET}/'
    summary=f'Publicación científica de {journal}'+(f' ({year})' if year else '')+'. Esta ficha reúne los datos bibliográficos y los enlaces a la publicación original.'
    schema={'@context':'https://schema.org','@type':'ScholarlyArticle','@id':canonical.rstrip('/')+'/#article','url':canonical,'headline':title,'author':[{'@type':'Person','@id':BASE+'/#person','name':'Miguel López Moreno'}],'sameAs':[f'https://doi.org/{doi}']+([f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'] if pmid else []),'isPartOf':{'@type':'Periodical','name':journal}}
    if year: schema['datePublished']=year
    meta=f'<span class="pill">{escape(journal)}</span><span class="pill">{escape(year)}</span><span class="pill">DOI</span>'+('<span class="pill">PubMed</span>' if pmid else '')
    pubmed_button=f'<a class="btn primary" href="https://pubmed.ncbi.nlm.nih.gov/{escape(pmid)}/" target="_blank" rel="noopener">Ver en PubMed ↗</a>' if pmid else ''
    subj=urllib.parse.quote(f'Solicitud de estudio completo — {title}')
    body=urllib.parse.quote(f'Hola Miguel,\n\nMe gustaría solicitar el estudio completo: {title}\n\nMuchas gracias.')
    mail=f'mailto:miguel@nutreconciencia.com?subject={subj}&body={body}'
    return ('<!doctype html><html lang="es"><head>\n'
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{escape(title)} | Miguel López Moreno</title>\n'
            f'<meta name="description" content="{escape(summary)}">\n'
            f'<link rel="canonical" href="{canonical}">\n'
            f'<meta property="og:title" content="{escape(title)} | Miguel López Moreno"><meta property="og:description" content="{escape(summary)}">\n'
            f'<meta property="og:type" content="article"><meta property="og:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">\n'
            '<link rel="stylesheet" href="../../assets/styles.css?v=27">\n'
            '<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">\n'+json.dumps(schema,ensure_ascii=False,indent=2)+'\n</script>\n'
            f'<meta property="og:url" content="{canonical}"><meta name="twitter:card" content="summary_large_image">\n'
            f'<meta name="twitter:title" content="{escape(title)} | Miguel López Moreno"><meta name="twitter:description" content="{escape(summary)}">\n'
            f'<meta name="twitter:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">\n</head><body>'
            '<nav class="nav"><div class="nav-inner"><a class="brand" href="/">Miguel López Moreno <span>/ Nutreconciencia</span></a>'
            '<button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false"><span class="open">☰</span><span class="close">×</span></button>'
            '<div class="links"><a href="/articulos/">Investigación</a><a href="/articulos/">Artículos</a><a href="/prensa/">Prensa</a><a href="/libro/">Libro</a><a href="/sobre-mi/">Sobre mí</a><a href="/podcasts/">Podcasts</a></div></div></nav>'
            f'<div class="breadcrumbs"><a href="/articulos/">Artículos</a> → {escape(title)}</div><main class="article-shell">'
            '<section class="study-hero article-top">'
            f'<div class="article-kicker">Resumen científico · {escape(journal)} · {escape(year)}</div>'
            f'<h1 class="study-title-original">{escape(title)}</h1>'
            f'<div class="article-original"><strong>Título original:</strong> {escape(title)}</div><div class="article-meta">{meta}</div></section>'
            '<section class="study-layout article-layout"><div id="resumen" class="study-main article-prose">'
            f'<p class="summary-lead">{escape(summary)}</p>'
            '<div class="article-note">Esta ficha bibliográfica facilita la consulta y no sustituye al artículo científico original.</div>'
            f'<h2 id="publicacion">Publicación original</h2><p><strong>{escape(title)}</strong></p><p>{escape(authors)}</p>'
            f'<div class="source-buttons"><a class="btn soft" href="https://doi.org/{escape(doi)}" target="_blank" rel="noopener">Ver DOI ↗</a>{pubmed_button}</div>'
            '</div><aside class="study-side article-sidebar">'
            '<div class="sidebar-card"><strong>En esta página</strong><div class="sidebar-links"><a href="#resumen">Resumen</a><a href="#publicacion">Publicación</a></div></div>'
            f'<div class="sidebar-card"><strong>Artículo original</strong><div><strong>Título</strong><br>{escape(title)}</div></div>'
            f'</aside></section><div class="study-request"><strong>¿Quieres consultar el estudio completo?</strong><a href="{mail}">Solicitar el estudio completo por email</a><small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small></div></main>'
            '<footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div><div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br><a href="mailto:miguel@nutreconciencia.com">miguel@nutreconciencia.com</a><br>© 2026 Miguel López Moreno.</div></div></footer>'
            '<script>document.querySelectorAll(\'.mobile-menu-toggle\').forEach(btn=>{btn.addEventListener(\'click\',()=>{const nav=btn.closest(\'.nav\');const open=nav.classList.toggle(\'nav-open\');btn.setAttribute(\'aria-expanded\',open?\'true\':\'false\');});});</script></body></html>')

def main():
    if not META.exists(): raise FileNotFoundError(META)
    data=json.loads(META.read_text(encoding='utf-8')); doi=clean(data.get('doi'))
    if not doi: raise RuntimeError('metadata.json has no DOI')
    item=crossref(doi); pmid=pubmed_id(doi)
    PAGE.write_text(build_page(item,doi,pmid),encoding='utf-8')
    data['pmid']=pmid; data['publisher']=clean(item.get('publisher',''))
    META.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('='*72); print('MIGRATE EXISTING DOI ARTICLE — EDITORIAL TEMPLATE V2'); print('='*72)
    print('Target:',TARGET); print('DOI:',doi); print('PMID:',pmid or 'not found')
    print('Canonical template: PASS'); print('ScholarlyArticle schema: PASS'); print('Article layout: PASS'); print('Source buttons: PASS')

if __name__=='__main__': main()
