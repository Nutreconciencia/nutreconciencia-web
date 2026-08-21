#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "index.html"

PERSON_SCHEMA = r'''
<script type="application/ld+json" id="nutreconciencia-person-schema">
{
  "@context": "https://schema.org",
  "@type": "Person",
  "@id": "https://nutreconciencia.com/#person",
  "name": "Miguel López Moreno",
  "url": "https://nutreconciencia.com/",
  "jobTitle": [
    "Investigador principal del grupo Dieta, Salud Planetaria y Rendimiento",
    "Codirector del Máster de Formación Permanente en Alimentación Plant-Based: Nutrición, industria y sostenibilidad"
  ],
  "worksFor": {
    "@type": "CollegeOrUniversity",
    "name": "Universidad Francisco de Vitoria",
    "url": "https://www.ufv.es/"
  },
  "affiliation": [
    {
      "@type": "CollegeOrUniversity",
      "name": "Universidad Pontificia de Salamanca",
      "url": "https://www.upsa.es/"
    },
    {
      "@type": "Organization",
      "name": "Fit Generation",
      "url": "https://fitgeneration.es/"
    }
  ],
  "sameAs": [
    "https://orcid.org/0000-0003-0553-6210",
    "https://scholar.google.com/citations?user=jCDnm6YAAAAJ&hl=es",
    "https://fitgeneration.es/equipo/miguel-lopez-moreno/",
    "https://www.instagram.com/nutreconciencia/"
  ]
}
</script>
'''

def main():
    if not HOME.exists():
        raise FileNotFoundError("index.html not found at repository root")

    text = HOME.read_text(encoding="utf-8")

    if '"@id": "https://nutreconciencia.com/#person"' in text:
        print("Person schema already present on homepage. No change made.")
        return

    marker = re.search(r"</head>", text, flags=re.I)
    if not marker:
        raise RuntimeError("Could not find </head> in index.html")

    updated = text[:marker.start()] + PERSON_SCHEMA.strip() + "\n" + text[marker.start():]
    HOME.write_text(updated, encoding="utf-8")

    print("Added canonical Person JSON-LD to /index.html")
    print("Person @id: https://nutreconciencia.com/#person")

if __name__ == "__main__":
    main()
