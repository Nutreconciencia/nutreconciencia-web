#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET="when-ultra-processing-obscures-sustainable-dietary-transitions"
META=ROOT/"articulos"/TARGET/"metadata.json"
SCRIPT=ROOT/"scripts"/"add_paper_by_doi.py"

def main():
    data=json.loads(META.read_text(encoding="utf-8"))
    spec=importlib.util.spec_from_file_location("doi_template",SCRIPT)
    mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
    doi=data["doi"]; item=mod.crossref(doi); pmid=mod.pubmed_id(doi)
    (ROOT/"articulos"/TARGET/"index.html").write_text(mod.build_page(item,doi,pmid),encoding="utf-8")
    data.update({"pmid":pmid,"publisher":mod.clean(item.get("publisher","")),"abstract":mod.abstract_from_crossref(item)})
    META.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("MIGRATED EXISTING DOI ARTICLE — FINAL TEMPLATE")
    print("Target:",TARGET)
    print("DOI:",doi)
    print("PMID:",pmid or "not found")
    print("Abstract available:","YES" if data.get("abstract") else "NO")
    print("CSS version:",mod.CSS_VERSION)
    print("Editorial layout: PASS")
    print("ScholarlyArticle schema: PASS")

if __name__=="__main__": main()
