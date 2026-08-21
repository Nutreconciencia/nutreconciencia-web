#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "libro" / "index.html"

REPLACEMENTS = {
    'href="../index.html"': 'href="/"',
    'href="../articulos/index.html"': 'href="/articulos/"',
    'href="../prensa/index.html"': 'href="/prensa/"',
    'href="../libro/index.html"': 'href="/libro/"',
    'href="../sobre-mi/index.html"': 'href="/sobre-mi/"',
    'href="../podcasts/index.html"': 'href="/podcasts/"',
    'href="../index.html#sobre-mi"': 'href="/#sobre-mi"',
}

EXPECTED = [
    'href="/"',
    'href="/articulos/"',
    'href="/prensa/"',
    'href="/libro/"',
    'href="/sobre-mi/"',
    'href="/podcasts/"',
    'href="/#sobre-mi"',
]

def main():
    if not PAGE.exists():
        raise FileNotFoundError("No existe libro/index.html")

    text = PAGE.read_text(encoding="utf-8", errors="ignore")
    updated = text

    for old, new in REPLACEMENTS.items():
        updated = updated.replace(old, new)

    PAGE.write_text(updated, encoding="utf-8")

    missing = [x for x in EXPECTED if x not in updated]
    if missing:
        print("MISSING:")
        for x in missing:
            print(" -", x)
        raise SystemExit(1)

    print("=" * 72)
    print("BOOK PAGE INTERNAL LINKS")
    print("=" * 72)
    for old, new in REPLACEMENTS.items():
        print(f"{old} -> {new}")
    print("All expected canonical links are present.")
    print("Updated: libro/index.html")

if __name__ == "__main__":
    main()
