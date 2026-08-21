#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "index.html"

REPLACEMENTS = {
    'href="index.html"': 'href="/"',
    'href="articulos/index.html"': 'href="/articulos/"',
    'href="prensa/index.html"': 'href="/prensa/"',
    'href="libro/index.html"': 'href="/libro/"',
    'href="sobre-mi/index.html"': 'href="/sobre-mi/"',
    'href="sobre-mi/"': 'href="/sobre-mi/"',
    'href="podcasts/index.html"': 'href="/podcasts/"',
    'href="articulos/plant-based-misinformation/index.html"':
        'href="/articulos/plant-based-misinformation/"',
    'href="articulos/omniveg/index.html"':
        'href="/articulos/omniveg/"',
    'href="articulos/appearance-of-validity/index.html"':
        'href="/articulos/appearance-of-validity/"',
}

EXPECTED = [
    'href="/"',
    'href="/articulos/"',
    'href="/prensa/"',
    'href="/libro/"',
    'href="/sobre-mi/"',
    'href="/podcasts/"',
    'href="/articulos/plant-based-misinformation/"',
    'href="/articulos/omniveg/"',
    'href="/articulos/appearance-of-validity/"',
]

def main():
    if not HOME.exists():
        raise FileNotFoundError("No existe index.html en la raíz del repositorio.")

    text = HOME.read_text(encoding="utf-8", errors="ignore")
    updated = text

    for old, new in REPLACEMENTS.items():
        updated = updated.replace(old, new)

    HOME.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("HOME NAVIGATION CANONICALIZATION")
    print("=" * 72)
    for old, new in REPLACEMENTS.items():
        print(f"{old} -> {new}")

    print("\nVERIFICATION")
    missing = [value for value in EXPECTED if value not in updated]
    if missing:
        print("MISSING:")
        for value in missing:
            print(f"  - {value}")
        raise SystemExit(1)

    print("All expected canonical links are present.")
    print("Updated: index.html")

if __name__ == "__main__":
    main()
