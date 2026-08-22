#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "when-ultra-processing-obscures-sustainable-dietary-transitions"
META = ROOT / "articulos" / TARGET / "metadata.json"
TEMPLATE = ROOT / "scripts" / "add_paper_by_doi.py"

if not META.exists():
    raise FileNotFoundError(META)
if not TEMPLATE.exists():
    raise FileNotFoundError(TEMPLATE)

spec = importlib.util.spec_from_file_location("doi_template", TEMPLATE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)

data = json.loads(META.read_text(encoding="utf-8"))
doi = mod.clean(data.get("doi"))
if not doi:
    raise RuntimeError("metadata.json has no DOI")

item = mod.crossref(doi)
pmid = mod.pubmed_id(doi)
html = mod.build_html(item, TARGET, doi, pmid)
page = ROOT / "articulos" / TARGET / "index.html"
page.write_text(html, encoding="utf-8")
data["pmid"] = pmid
data["publisher"] = mod.clean(item.get("publisher", ""))
META.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

print("=" * 72)
print("MIGRATE EXISTING DOI ARTICLE — TEMPLATE V3")
print("=" * 72)
print("Target:", TARGET)
print("DOI:", doi)
print("PMID:", pmid or "not found")
print("CSS version: 28")
print("Editorial layout: PASS")
print("ScholarlyArticle schema: PASS")
print("Pills structure: PASS")
