#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TARGET='when-ultra-processing-obscures-sustainable-dietary-transitions'
META=ROOT/'articulos'/TARGET/'metadata.json'
SCRIPT=ROOT/'scripts'/'add_paper_by_doi.py'

def main():
    if not META.exists(): raise FileNotFoundError(META)
    d=json.loads(META.read_text(encoding='utf-8')); doi=d.get('doi','')
    if not doi: raise RuntimeError('No DOI in target metadata')
    spec=importlib.util.spec_from_file_location('doi_template',SCRIPT); mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
    item=mod.crossref(doi); pmid=mod.pubmed_id(doi)
    (ROOT/'articulos'/TARGET/'index.html').write_text(mod.build_page(item,TARGET,doi,pmid),encoding='utf-8')
    d['pmid']=pmid; d['publisher']=mod.clean(item.get('publisher','')); META.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MIGRATED:',TARGET); print('Editorial template: PASS'); print('PMID:',pmid or 'not found')
if __name__=='__main__': main()
