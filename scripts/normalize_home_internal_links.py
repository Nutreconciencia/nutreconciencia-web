#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "index.html"

# Only normalize canonical internal URLs in the homepage.
REPLACEMENTS = {
    'href="index.html"': 'href="/"',
    'href="articulos/index.html"': 'href="/articulos/"',
    'href="prensa/index.html"': 'href="/prensa/"',
    'href="libro/index.html"': 'href="/libro/"',
    'href="podcasts/index.html"': 'href="/podcasts/"',
    'href="articulos/plant-based-misinformation/index.html"':
        'href="/articulos/plant-based-misinformation/"',
    'href="articulos/omniveg/index.html"':
        'href="/articulos/omniveg/"',
    'href="articulos/appearance-of-validity/index.html"':
        'href="/articulos/appearance-of-validity/"',
}

def main():
    if not HOME.exists():
        raise FileNotFoundError("index.html not found")

    text = HOME.read_text(encoding="utf-8", errors="ignore")
    updated = text

    for old, new in REPLACEMENTS.items():
        updated = updated.replace(old, new)

    # Avoid touching external links or article content.
    HOME.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("HOME NAVIGATION CANONICALIZATION")
    print("=" * 72)
    for old, new in REPLACEMENTS.items():
        print(f"{old} -> {new}")

    print("Updated: index.html")

if __name__ == "__main__":
    main()
