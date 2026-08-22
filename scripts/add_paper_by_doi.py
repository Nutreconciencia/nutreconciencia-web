#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'articulos'
BASE = 'https://nutreconciencia.com'
PERSON = BASE + '/#person'
CSS_VERSION = '28'
UA = 'NutreconcienciaWeb/1.0 (https://nutreconciencia.com/)'

def clean(v): return re.sub(r'\s+', ' ', v or '').strip()

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode())

def get_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept':'application/xml,text/xml,*/*'})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read().decode('utf-8', errors='replace')

def crossref(doi):
    return get_json('https://api.crossref.org/works/' + urllib.parse.quote(doi, safe=''))['message']

def pubmed_id(doi):
    term = urllib.parse.quote(f'{doi}[DOI]', safe='')
    url = ('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
           f'?db=pubmed&term={term}&retmode=json&tool=nutreconciencia_web'
           '&email=miguel@nutreconciencia.com')
    try:
        ids = get_json(url).get('esearchresult', {}).get('idlist', [])
        return ids[0] if ids else ''
    except Exception:
        return ''

def pubmed_abstract(pmid):
    if not pmid: return ''
    url = ('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
           f'?db=pubmed&id={urllib.parse.quote(pmid)}&retmode=xml'
           '&tool=nutreconciencia_web&email=miguel@nutreconciencia.com')
    try:
        root = ET.fromstring(get_text(url))
        parts=[]
        for node in root.findall('.//AbstractText'):
            txt=''.join(node.itertext()).strip()
            if not txt: continue
            label=node.attrib.get('Label')
            if label and not txt.startswith(label + ':'): txt=f'{label}: {txt}'
            parts.append(txt)
        return '\n\n'.join(parts).strip()
    except Exception:
        return ''

def year_of(item):
    for key in ('published-print','published-online','issued','created'):
        parts=item.get(key,{}).get('date-parts',[])
        if parts and parts[0]: return str(parts[0][0])
    return ''

def authors_of(item):
    out=[]
    for a in item.get('author',[]):
        n=clean(f"{a.get('given','')} {a.get('family','')}")
        if n: out.append(n)
    return out

def slugify(title):
    s=clean(title).lower().translate(str.maketrans('áéíóúüñ','aeiouun'))
    return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',s)).strip('-')[:120]

def page(item, doi, slug, pmid, abstract):
    title=clean((item.get('title') or [''])[0]); journal=clean((item.get('container-title') or [''])[0]) or 'Scientific publication'; year=year_of(item); authors=', '.join(authors_of(item)); canonical=f'{BASE}/articulos/{slug}/'; doi_url=f'https://doi.org/{doi}'
    summary=abstract if abstract else f'Publicación científica de {journal}' + (f' ({year}).' if year else '.')
    schema={'@context':'https://schema.org','@type':'ScholarlyArticle','@id':canonical.rstrip('/')+'/#article','url':canonical,'headline':title,'author':[{'@type':'Person','@id':PERSON,'name':'Miguel López Moreno'}],'sameAs':[doi_url]+([f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'] if pmid else []),'isPartOf':{'@type':'Periodical','name':journal}}
    if year: schema['datePublished']=year
    if abstract: schema['description']=abstract
    meta=f'<span class="pill">{escape(journal)}</span><span class="pill">{escape(year)}</span><span class="pill">DOI</span>'+('<span class="pill">PubMed</span>' if pmid else '')
    pubmed_button=f'<a class="btn primary" href="https://pubmed.ncbi.nlm.nih.gov/{escape(pmid)}/" target="_blank" rel="noopener">Ver en PubMed ↗</a>' if pmid else ''
    note=('El resumen se basa en el abstract disponible en PubMed y no sustituye al artículo científico original.' if abstract else 'No se encontró un abstract estructurado en PubMed; esta ficha contiene información bibliográfica.')
    if abstract:
        summary_html=f'<p class="summary-lead">{escape(abstract)}</p><div class="article-note">{note}</div><h2 id="s1">Resumen del artículo</h2><p>{escape(abstract)}</p>'
    else:
        summary_html=f'<p class="summary-lead">{escape(summary)}</p><div class="article-note">{note}</div><h2 id="s1">Sobre esta publicación</h2><p>Esta ficha reúne los datos bibliográficos de la publicación y enlaza directamente con la fuente científica original.</p>'
    subject=urllib.parse.quote(f'Solicitud de estudio completo — {title}'); body=urllib.parse.quote(f'Hola Miguel,\n\nMe gustaría solicitar el estudio completo: {title}\n\nMuchas gracias.'); mail=f'mailto:miguel@nutreconciencia.com?subject={subject}&body={body}'
    return f'''<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | Miguel López Moreno</title><meta name="description" content="{escape(summary[:300])}">
<link rel="canonical" href="{canonical}"><meta property="og:title" content="{escape(title)} | Miguel López Moreno"><meta property="og:description" content="{escape(summary[:300])}"><meta property="og:type" content="article"><meta property="og:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
<link rel="stylesheet" href="../../assets/styles.css?v={CSS_VERSION}">
<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">{json.dumps(schema,ensure_ascii=False,indent=2)}</script>
<meta property="og:url" content="{canonical}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{escape(title)} | Miguel López Moreno"><meta name="twitter:description" content="{escape(summary[:300])}"><meta name="twitter:image" content="{BASE}/assets/miguel-lopez-moreno.jpg">
</head><body><nav class="nav"><div class="nav-inner"><a class="brand" href="/">Miguel López Moreno <span>/ Nutreconciencia</span></a><button class="mobile-menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false"><span class="open">☰</span><span class="close">×</span></button><div class="links"><a href="/articulos/">Investigación</a><a href="/articulos/">Artículos</a><a href="/prensa/">Prensa</a><a href="/libro/">Libro</a><a href="/sobre-mi/">Sobre mí</a><a href="/podcasts/">Podcasts</a></div></div></nav>
<div class="breadcrumbs"><a href="/articulos/">Artículos</a> → {escape(title)}</div><main class="article-shell"><section class="study-hero article-top"><div class="article-kicker">Resumen científico · {escape(journal)} · {escape(year)}</div><h1 class="study-title-original">{escape(title)}</h1><div class="article-original"><strong>Título original:</strong> {escape(title)}</div><div class="article-meta">{meta}</div></section>
<section class="study-layout article-layout"><div id="resumen" class="study-main article-prose">{summary_html}<h2 id="publicacion">Publicación original</h2><p><strong>{escape(title)}</strong></p><p>{escape(authors)}</p><div class="source-buttons"><a class="btn soft" href="{doi_url}" target="_blank" rel="noopener">Ver DOI ↗</a>{pubmed_button}</div></div><aside class="study-side article-sidebar"><div class="sidebar-card"><strong>En esta página</strong><div class="sidebar-links"><a href="#resumen">Resumen</a><a href="#s1">{'Resumen del artículo' if abstract else 'Sobre esta publicación'}</a><a href="#publicacion">Publicación</a></div></div><div class="sidebar-card"><strong>Artículo original</strong><div><strong>Título</strong><br>{escape(title)}</div></div></aside></section>
<div class="study-request"><strong>¿Quieres consultar el estudio completo?</strong><a href="{mail}">Solicitar el estudio completo por email</a><small>Se abrirá un correo dirigido a miguel@nutreconciencia.com.</small></div></main><footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div><div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br><a href="mailto:miguel@nutreconciencia.com">miguel@nutreconciencia.com</a><br>© 2026 Miguel López Moreno.</div></div></footer><script>document.querySelectorAll('.mobile-menu-toggle').forEach(btn=>{btn.addEventListener('click',()=>{const nav=btn.closest('.nav');const open=nav.classList.toggle('nav-open');btn.setAttribute('aria-expanded',open?'true':'false');});});</script></body></html>'''

def main():
    if len(sys.argv)!=2: raise SystemExit('Uso: python add_paper_by_doi.py DOI')
    doi=clean(sys.argv[1]).replace('https://doi.org/','').strip('/'); item=crossref(doi); title=clean((item.get('title') or [''])[0])
    if not title: raise RuntimeError('Crossref no devolvió título')
    slug=slugify(title); folder=ART/slug
    if folder.exists(): raise RuntimeError(f'La carpeta ya existe: {folder}')
    pmid=pubmed_id(doi); abstract=pubmed_abstract(pmid); folder.mkdir(parents=True)
    (folder/'index.html').write_text(page(item,doi,slug,pmid,abstract),encoding='utf-8')
    metadata={'doi':doi,'title':title,'authors':authors_of(item),'journal':clean((item.get('container-title') or [''])[0]),'publisher':clean(item.get('publisher','')),'year':year_of(item),'pmid':pmid,'abstract':abstract}
    (folder/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print('='*72); print('NEW PAPER CREATED — DOI + PUBMED ABSTRACT'); print('='*72); print('DOI:',doi); print('Title:',title); print('Slug:',slug); print('PMID:',pmid or 'not found'); print('Abstract:','FOUND' if abstract else 'NOT FOUND'); print('CSS version:',CSS_VERSION); print('ScholarlyArticle schema: PASS')

if __name__=='__main__': main()

