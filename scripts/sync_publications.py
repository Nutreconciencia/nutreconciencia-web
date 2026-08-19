#!/usr/bin/env python3
import json, re, urllib.parse, urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"articulos"
ORCID="0000-0003-0553-6210"
AUTHOR_RE=re.compile(r"(?:^|\s)miguel(?:\s|-)+l(?:ó|o)pez(?:[-\s]?moreno)?$", re.I)

def get(url, headers=None):
    req=urllib.request.Request(url, headers={"User-Agent":"Nutreconciencia research sync/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def strip_xml(s):
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",s or "")).strip()

def slugify(s):
    s=(s.lower().encode("ascii","ignore").decode("ascii"))
    s=re.sub(r"[^a-z0-9]+","-",s).strip("-")
    return s[:90]

def extractive_summary(abstract):
    if not abstract:
        return "Resumen pendiente de revisión editorial."
    parts=re.split(r'(?<=[.!?])\s+',abstract.strip())
    return " ".join(parts[:3])[:700]

def get_crossref():
    url=("https://api.crossref.org/v1/works?filter="
         "orcid:0000-0003-0553-6210,type:journal-article&rows=200"
         "&select=DOI,title,author,published,container-title,URL")
    req=urllib.request.Request(url,headers={"User-Agent":"Nutreconciencia research sync/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        data=json.loads(r.read().decode())
    out=[]
    for item in data.get("message",{}).get("items",[]):
        title=((item.get("title") or [""])[0]).strip()
        authors=item.get("author") or []
        match=False
        for a in authors:
            orcid=(a.get("ORCID") or "").replace("https://orcid.org/","")
            name=(a.get("given","")+" "+a.get("family","")).lower()
            if orcid=="0000-0003-0553-6210" or ("miguel" in name and ("lopez" in name or "lópez" in name)):
                match=True
        if not title or not match: continue
        parts=((item.get("published") or {}).get("date-parts") or [[]])[0]
        year=str(parts[0]) if parts else ""
        out.append({
            "title":title,
            "journal":((item.get("container-title") or [""])[0]),
            "year":year,
            "doi":(item.get("DOI") or "").strip(),
            "pubmed":"",
            "abstract":"",
            "authors":[(" ".join(x for x in [a.get("given",""),a.get("family","")] if x).strip()) for a in authors if a.get("family")]
        })
    return out

def get_pubmed():
    q='("Lopez-Moreno M"[Author] OR "López-Moreno M"[Author] OR "López Moreno M"[Author])'
    url=f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={urllib.parse.quote(q)}&retmax=500&sort=pub+date&retmode=json"
    ids=json.loads(get(url).decode())["esearchresult"]["idlist"]
    if not ids:return []
    x=get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id="+",".join(ids)+"&retmode=xml")
    root=ET.fromstring(x); out=[]
    for art in root.findall(".//PubmedArticle"):
        title_node=art.find(".//ArticleTitle")
        title="".join(title_node.itertext()).strip() if title_node is not None else ""
        authors=[]
        for au in art.findall(".//Author"):
            fam=au.findtext("LastName") or ""
            giv=au.findtext("ForeName") or ""
            authors.append((giv+" "+fam).strip())
        match=any(("miguel" in a.lower() and ("lopez" in a.lower() or "lópez" in a.lower())) for a in authors)
        if not match or not title: continue
        pmid=art.findtext(".//PMID") or ""
        journal=art.findtext(".//Journal/Title") or ""
        year=(art.findtext(".//PubDate/Year") or art.findtext(".//PubDate/MedlineDate") or "")[:4]
        doi=""
        for aid in art.findall(".//ArticleId"):
            if aid.get("IdType")=="doi": doi=(aid.text or "").strip()
        absn=art.findall(".//Abstract/AbstractText")
        abstract=" ".join("".join(n.itertext()) for n in absn).strip()
        out.append({"title":title,"journal":journal,"year":year,"doi":doi,
                    "pubmed":f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "abstract":abstract,"authors":authors})
    return out

def merged_publications():
    items={}
    for a in get_crossref()+get_pubmed():
        key=(a.get("doi") or a.get("title","")).lower().strip()
        if not key: continue
        if key not in items:
            items[key]=a
        else:
            # PubMed usually provides the stronger abstract + PMID; merge it in.
            cur=items[key]
            for k in ["pubmed","abstract","journal","year","authors","doi"]:
                if a.get(k) and not cur.get(k):
                    cur[k]=a[k]
            if a.get("abstract"):
                cur["abstract"]=a["abstract"]
            if a.get("pubmed"):
                cur["pubmed"]=a["pubmed"]
    return list(items.values())

def render(a):
    slug=slugify(a["title"])
    d=ART/slug; d.mkdir(exist_ok=True)
    summary=extractive_summary(a["abstract"])
    title_es=a["title"]  # can be translated/editorially refined later
    tags="PubMed · "+a["journal"]
    html=f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title_es} | Miguel López Moreno</title><meta name="description" content="{summary[:220]}"><link rel="canonical" href="https://nutreconciencia.com/articulos/{slug}/"><link rel="stylesheet" href="../../assets/styles.css"></head><body><nav class="nav"><div class="nav-inner"><a class="brand" href="../../index.html">Miguel López Moreno <span>/ Nutreconciencia</span></a><div class="links"><a href="../../index.html#investigacion">Investigación</a><a href="../index.html">Artículos</a><a href="../../prensa/index.html">Prensa</a><a href="../../libro/index.html">Libro</a><a href="../../sobre-mi/index.html">Sobre mí</a></div></div></nav><div class="breadcrumbs"><a href="../index.html">Artículos</a> → {title_es}</div><section class="study-hero"><div class="kicker">Resumen científico · {a["journal"]} · {a["year"]}</div><h1>{title_es}</h1><div class="study-original"><strong>Título original:</strong> <em>{a["title"]}</em></div><div class="study-meta"><span class="pill">{a["journal"]}</span><span class="pill">{a["year"]}</span><span class="pill">PubMed</span></div></section><section class="study-layout"><article class="study-main"><p class="study-summary">{summary}</p><div class="study-note">Resumen automático basado en el registro bibliográfico disponible. Para la interpretación completa, métodos y resultados, consulta el artículo original.</div><h2>La pregunta</h2><p>¿Qué pregunta aborda este trabajo y qué aporta a la literatura científica?</p><h2>Qué aporta</h2><p>La ficha se genera a partir de metadatos y del resumen bibliográfico. Se conservará el enlace al registro de PubMed para consultar la publicación original.</p><h2>Publicación original</h2><p>{a["title"]} · <em>{a["journal"]}</em>, {a["year"]}.</p><div class="source-buttons"><a class="btn primary" href="{a["pubmed"]}" target="_blank" rel="noopener">Ver en PubMed ↗</a>{f'<a class="btn soft" href="https://doi.org/{a["doi"]}" target="_blank" rel="noopener">Ver DOI ↗</a>' if a["doi"] else ''}</div></article><aside class="study-side"><div class="study-card"><strong>Fuente académica</strong><div>PubMed</div><a class="btn primary" href="{a["pubmed"]}" target="_blank" rel="noopener">Abrir ficha ↗</a></div><div class="study-card"><strong>Autores</strong><div>{"; ".join(a["authors"])}</div></div></aside></section><footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div><div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br>© 2026 Miguel López Moreno.</div></div></footer></body></html>"""
    (d/"index.html").write_text(html,encoding="utf-8")
    return slug,a

if __name__=="__main__":
    pubs=merged_publications()
    print("PubMed records found:",len(pubs))
    for a in pubs: render(a)
