#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

ROOT=Path(__file__).resolve().parents[1]
MAP=ROOT/"definitive_publication_map.csv"
ART=ROOT/"articulos"
PRESS=ROOT/"prensa"
SITEMAP=ROOT/"sitemap.xml"
BASE="https://nutreconciencia.com"
SECTIONS=[f"{BASE}/",f"{BASE}/articulos/",f"{BASE}/prensa/",f"{BASE}/libro/",f"{BASE}/sobre-mi/",f"{BASE}/podcasts/"]

def clean(v): return re.sub(r"\s+"," ",v or "").strip()

def established():
    if not MAP.exists(): raise FileNotFoundError(MAP)
    with MAP.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    slugs={clean(r.get("slug")) for r in rows if clean(r.get("is_canonical")).lower()=="true"}-{" "}
    slugs.discard("")
    if len(slugs)!=51: raise RuntimeError(f"Expected 51 established canonical slugs; found {len(slugs)}")
    return slugs

def doi_articles():
    out=set()
    for meta in ART.glob("*/metadata.json"):
        d=json.loads(meta.read_text(encoding="utf-8"))
        if not clean(d.get("doi")): continue
        slug=meta.parent.name
        page=meta.parent/"index.html"
        if not page.exists(): raise RuntimeError(f"metadata.json without index.html: {slug}")
        text=page.read_text(encoding="utf-8",errors="ignore")
        if f'<link rel="canonical" href="{BASE}/articulos/{slug}/">' not in text:
            raise RuntimeError(f"DOI article canonical missing: {slug}")
        if 'id="nutreconciencia-scholarly-article-schema"' not in text:
            raise RuntimeError(f"ScholarlyArticle schema missing from DOI article: {slug}")
        if '"https://nutreconciencia.com/#person"' not in text:
            raise RuntimeError(f"#person author link missing from DOI article: {slug}")
        out.add(slug)
    return out

def established_urls(slugs):
    out=set()
    for slug in slugs:
        page=ART/slug/"index.html"
        if not page.exists(): raise RuntimeError(f"Established article index missing: {slug}")
        text=page.read_text(encoding="utf-8",errors="ignore")
        if f'<link rel="canonical" href="{BASE}/articulos/{slug}/">' not in text:
            raise RuntimeError(f"Established article canonical missing: {slug}")
        out.add(f"{BASE}/articulos/{slug}/")
    return out

def press_urls():
    out=set()
    for page in PRESS.glob("*/index.html"):
        text=page.read_text(encoding="utf-8",errors="ignore")
        m=re.search(r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',text,re.I|re.S)
        if not m: raise RuntimeError(f"Press canonical missing: {page}")
        url=clean(m.group(1))
        if not url.startswith(f"{BASE}/prensa/"): raise RuntimeError(f"Bad press canonical: {url}")
        out.add(url)
    if len(out)!=19: raise RuntimeError(f"Expected 19 press URLs; found {len(out)}")
    return out

def build(urls):
    root=Element("urlset",{"xmlns":"http://www.sitemaps.org/schemas/sitemap/0.9"})
    for url in sorted(urls):
        u=SubElement(root,"url"); loc=SubElement(u,"loc"); loc.text=url
    raw=tostring(root,encoding="utf-8")
    s=minidom.parseString(raw).toprettyxml(indent="  ",encoding="UTF-8").decode()
    return s.replace('<?xml version="1.0" encoding="UTF-8"?>\n\n','<?xml version="1.0" encoding="UTF-8"?>\n')

def main():
    old=established(); new=doi_articles(); articles=established_urls(old)
    presses=press_urls()
    urls=set(SECTIONS)|presses|articles|{f"{BASE}/articulos/{s}/" for s in new}
    expected=f"{BASE}/articulos/when-ultra-processing-obscures-sustainable-dietary-transitions/"
    if expected not in urls: raise RuntimeError("Expected new DOI article missing")
    SITEMAP.write_text(build(urls),encoding="utf-8")
    locs=re.findall(r"<loc>([^<]+)</loc>",SITEMAP.read_text(encoding="utf-8"))
    if len(locs)!=len(set(locs)): raise RuntimeError("Duplicate sitemap URLs")
    if any("https://nutreconciencia.com/https://" in u for u in locs): raise RuntimeError("Malformed duplicated-domain URL")
    print("="*72)
    print("STEP 9A FINAL V2 — REBUILD VALID XML SITEMAP")
    print("="*72)
    print(f"Section URLs: {len(SECTIONS)}")
    print(f"Press URLs: {len(presses)}")
    print(f"Established article URLs: {len(old)}")
    print(f"New DOI article URLs: {len(new)}")
    print(f"Total sitemap URLs: {len(urls)}")
    print("Established article canonical validation: PASS")
    print("New DOI schema validation: PASS")
    print("XML structure: PASS")
    print("Duplicate URL check: PASS")
    print("Malformed duplicated-domain URL check: PASS")
    print("New DOI article present: PASS")
    print("sitemap.xml: REBUILT")
if __name__=="__main__": main()
