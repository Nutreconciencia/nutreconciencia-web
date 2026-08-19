#!/usr/bin/env python3
import html, re, urllib.parse, urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PRESS=ROOT/"prensa"
PRESS.mkdir(exist_ok=True)

QUERIES=['"Miguel López Moreno" nutrición','"Miguel López Moreno" Nutreconciencia','"Miguel López Moreno" nutrition']

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Nutreconciencia press sync/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read()

def clean(s):
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",s or "")).strip()

def slugify(s):
    s=re.sub(r"[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ]+","-",s.lower()).strip("-")
    return s[:85]

def render(title,source,date,url):
    slug=slugify(source+"-"+title)
    d=PRESS/slug; d.mkdir(exist_ok=True)
    page=f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} | Miguel López Moreno</title><meta name="description" content="Aparición de Miguel López Moreno en {html.escape(source)}."><link rel="canonical" href="https://nutreconciencia.com/prensa/{slug}/"><link rel="stylesheet" href="../../assets/styles.css"></head><body><nav class="nav"><div class="nav-inner"><a class="brand" href="../../index.html">Miguel López Moreno <span>/ Nutreconciencia</span></a><div class="links"><a href="../../index.html#investigacion">Investigación</a><a href="../../articulos/index.html">Artículos</a><a href="../index.html">Prensa</a><a href="../../libro/index.html">Libro</a><a href="../../sobre-mi/index.html">Sobre mí</a></div></div></nav><main class="media-article-shell"><div class="news-paper"><header class="news-masthead"><div class="logo">{html.escape(source)}</div><div class="sub">Aparición de Miguel López Moreno · {html.escape(date)}</div></header><article class="news-body"><div class="news-tag">EN MEDIOS</div><h1>{html.escape(title)}</h1><p class="news-deck">Nueva aparición o mención detectada en medios. La ficha resume y contextualiza la publicación sin reproducir su contenido.</p><div class="news-rule"></div><div class="news-meta"><span>{html.escape(source)}</span><span>{html.escape(date)}</span></div><div class="news-feature"><strong>Fuente original</strong><div>{html.escape(source)} · {html.escape(date)}</div></div><p>Esta ficha se crea automáticamente a partir del índice de noticias. Comprueba siempre la noticia original antes de utilizarla como fuente.</p><div class="news-actions"><a class="btn primary" href="{html.escape(url)}" target="_blank" rel="noopener">Leer la noticia original ↗</a><a class="btn soft" href="../index.html">Volver a prensa</a></div></article></div></main><footer><div class="footer-inner"><div><div style="font-family:Georgia,serif;font-size:32px">Miguel López Moreno</div><div style="margin-top:6px">@nutreconciencia</div></div><div class="footer-note">Ciencia de la nutrición, investigación y divulgación.<br>© 2026 Miguel López Moreno.</div></div></footer></body></html>"""
    (d/"index.html").write_text(page,encoding="utf-8")

seen=set()
for p in PRESS.glob("*/index.html"):
    t=p.read_text(encoding="utf-8")
    m=re.search(r'<meta property="og:title" content="([^"]+)',t)
    if m: seen.add(m.group(1).strip().lower())

for q in QUERIES:
    feed="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=es&gl=ES&ceid=ES:es"
    try:
        root=ET.fromstring(fetch(feed))
    except Exception:
        continue
    for item in root.findall(".//item"):
        title=clean(item.findtext("title"))
        link=(item.findtext("link") or "").strip()
        source=clean(item.findtext("source") or "Google News")
        date=clean(item.findtext("pubDate") or "")
        if not title or not link or title.lower() in seen: continue
        render(title,source,date,link)
        seen.add(title.lower())
