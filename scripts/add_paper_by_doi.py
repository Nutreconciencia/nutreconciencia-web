#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys, urllib.parse, urllib.request
from pathlib import Path
from html import escape

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"articulos"
BASE="https://nutreconciencia.com/"
PERSON=BASE+"#person"
UA="NutreconcienciaWeb/1.0 (https://nutreconciencia.com/)"

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode())

def clean(v): return re.sub(r"\s+"," ",v or "").strip()

def slugify(s):
    trans=str.maketrans("áéíóúüñ","aeiouun")
    s=clean(s).lower().translate(trans)
    return re.sub(r"-+","-",re.sub(r"[^a-z0-9]+","-",s)).strip("-")[:120].rstrip("-")

def crossref(doi):
    u="https://api.crossref.org/works/"+urllib.parse.quote(doi,safe="")
    return get_json(u)["message"]

def pubmed_id(doi):
    term=urllib.parse.quote(f"{doi}[DOI]",safe="")
    u=("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
       f"?db=pubmed&term={term}&retmode=json&tool=nutreconciencia_web"
       "&email=miguel@nutreconciencia.com")
    try:
        ids=get_json(u).get("esearchresult",{}).get("idlist",[])
        return ids[0] if ids else ""
    except Exception as e:
        print("PubMed lookup skipped:",e)
        return ""

def year(item):
    for key in ("published-print","published-online","issued","created"):
        parts=item.get(key,{}).get("date-parts",[])
        if parts and parts[0]: return str(parts[0][0])
    return ""

def authors(item):
    out=[]
    for a in item.get("author",[]):
        n=clean((a.get("given","")+" "+a.get("family","")).strip())
        if n: out.append(n)
    return out

def make_page(item,slug,doi,pmid):
    title=clean((item.get("title") or [""])[0])
    journal=clean((item.get("container-title") or [""])[0])
    yr=year(item)
    canon=f"{BASE}articulos/{slug}/"
    desc=f"{title}. Publicación científica de {journal}." if journal else f"{title}."
    schema={
      "@context":"https://schema.org","@type":"ScholarlyArticle",
      "@id":canon.rstrip("/")+"/#article","url":canon,"headline":title,
      "author":{"@type":"Person","@id":PERSON,"name":"Miguel López Moreno"},
      "sameAs":[f"https://doi.org/{doi}"] + ([f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"] if pmid else [])
    }
    if yr: schema["datePublished"]=yr
    if journal: schema["isPartOf"]={"@type":"Periodical","name":journal}
    pm=f'<a class="btn primary" href="https://pubmed.ncbi.nlm.nih.gov/{escape(pmid)}/" target="_blank" rel="noopener">Ver en PubMed ↗</a>' if pmid else ""
    author_text=", ".join(authors(item))
    return """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ | Miguel López Moreno</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANON__">
<meta property="og:title" content="__TITLE__ | Miguel López Moreno">
<meta property="og:description" content="__DESC__">
<meta property="og:type" content="article"><meta property="og:url" content="__CANON__">
<meta property="og:image" content="__IMAGE__">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__ | Miguel López Moreno">
<meta name="twitter:description" content="__DESC__">
<meta name="twitter:image" content="__IMAGE__">
<script type="application/ld+json" id="nutreconciencia-scholarly-article-schema">
__SCHEMA__
</script><link rel="stylesheet" href="../../assets/styles.css?v=27">
</head><body>
<nav class="nav"><div class="nav-inner"><a class="brand" href="/">Miguel López Moreno <span>/ Nutreconciencia</span></a>
<div class="links"><a href="/articulos/">Investigación</a><a href="/prensa/">Prensa</a><a href="/libro/">Libro</a><a href="/sobre-mi/">Sobre mí</a><a href="/podcasts/">Podcasts</a></div></div></nav>
<main class="article-shell"><section class="study-hero article-top">
<div class="article-kicker">Publicación científica · __JOURNAL__ · __YEAR__</div>
<h1 class="study-title-original">__TITLE__</h1>
<div class="article-original"><strong>Autores:</strong> __AUTHORS__</div>
</section>
<section class="study-layout article-layout"><div class="study-main article-prose">
<p class="summary-lead">Publicación científica de __JOURNAL__.</p>
<div class="article-note">Esta ficha reúne los datos bibliográficos de la publicación original y no sustituye el artículo científico completo.</div>
<h2>Publicación original</h2><p>__TITLE__</p>
<div class="source-buttons"><a class="btn soft" href="https://doi.org/__DOI__" target="_blank" rel="noopener">Ver DOI ↗</a>__PM__</div>
</div></section></main></body></html>
""".replace("__TITLE__",escape(title)).replace("__DESC__",escape(desc)).replace("__CANON__",canon).replace("__IMAGE__",BASE+"assets/miguel-lopez-moreno.jpg").replace("__SCHEMA__",json.dumps(schema,ensure_ascii=False,indent=2)).replace("__JOURNAL__",escape(journal)).replace("__YEAR__",escape(yr)).replace("__AUTHORS__",escape(author_text)).replace("__DOI__",escape(doi)).replace("__PM__",pm)

def main():
    if len(sys.argv)!=2: raise SystemExit("Uso: python add_paper_by_doi.py DOI")
    doi=clean(sys.argv[1]).replace("https://doi.org/","").strip("/")
    item=crossref(doi)
    title=clean((item.get("title") or [""])[0])
    if not title: raise RuntimeError("Crossref no devolvió título")
    slug=slugify(title)
    folder=ART/slug
    if folder.exists(): raise RuntimeError(f"La carpeta ya existe: {folder}")
    pmid=pubmed_id(doi)
    folder.mkdir(parents=True)
    (folder/"index.html").write_text(make_page(item,slug,doi,pmid),encoding="utf-8")
    (folder/"metadata.json").write_text(json.dumps({
      "doi":doi,"title":title,"authors":authors(item),
      "journal":clean((item.get("container-title") or [""])[0]),
      "year":year(item),"pmid":pmid
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print("NEW PAPER CREATED")
    print("DOI:",doi); print("Title:",title); print("Slug:",slug); print("PMID:",pmid or "not found")

if __name__=="__main__": main()
