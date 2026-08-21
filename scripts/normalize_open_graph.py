#!/usr/bin/env python3
"""
STEP 6 — Normalize Open Graph / Twitter metadata site-wide.

Modifies HTML pages in the repository:
- og:title
- og:description
- og:type
- og:url
- og:image
- twitter:card
- twitter:title
- twitter:description
- twitter:image

Rules:
- og:url comes from the page canonical URL when available.
- og:image is always absolute.
- /libro/ uses assets/comer-mentiras.jpg.
- Other pages use assets/miguel-lopez-moreno.jpg unless an existing absolute
  or site-local image explicitly points to a different asset.
- Existing title/description values are preserved.
- No changes to sitemap, .htaccess, JSON-LD, article content or navigation.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://nutreconciencia.com/"
DEFAULT_IMAGE = BASE + "assets/miguel-lopez-moreno.jpg"
BOOK_IMAGE = BASE + "assets/comer-mentiras.jpg"


META_RE = re.compile(
    r'<meta\b(?P<attrs>[^>]*?)\s*/?>',
    flags=re.I | re.S
)


def attr(attrs: str, name: str) -> str:
    m = re.search(
        rf'\b{name}\s*=\s*(["\'])(.*?)\1',
        attrs,
        flags=re.I | re.S,
    )
    return m.group(2).strip() if m else ""


def set_attr(attrs: str, name: str, value: str) -> str:
    pattern = re.compile(
        rf'(\b{name}\s*=\s*)(["\']).*?\2',
        flags=re.I | re.S,
    )
    if pattern.search(attrs):
        return pattern.sub(
            lambda m: m.group(1) + '"' + value.replace('"', "&quot;") + '"',
            attrs,
            count=1,
        )
    return attrs.rstrip() + f' {name}="{value}"'


def replace_or_add_meta(text: str, key_attr: str, key_value: str, content: str) -> str:
    matches = list(META_RE.finditer(text))
    for m in matches:
        attrs = m.group("attrs")
        if attr(attrs, key_attr).lower() == key_value.lower():
            new_attrs = set_attr(attrs, "content", content)
            replacement = "<meta" + new_attrs + ">"
            return text[:m.start()] + replacement + text[m.end():]

    marker = re.search(r"</head>", text, flags=re.I)
    if not marker:
        raise RuntimeError("No </head> found")
    tag = f'<meta {key_attr}="{key_value}" content="{content}">\n'
    return text[:marker.start()] + tag + text[marker.start():]


def get_meta(text: str, key_attr: str, key_value: str) -> str:
    for m in META_RE.finditer(text):
        attrs = m.group("attrs")
        if attr(attrs, key_attr).lower() == key_value.lower():
            return attr(attrs, "content")
    return ""


def get_canonical(text: str) -> str:
    m = re.search(
        r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
        text,
        flags=re.I | re.S,
    )
    if not m:
        return ""
    return urljoin(BASE, m.group(1).strip())


def choose_image(path: Path, existing: str) -> str:
    rel = path.relative_to(ROOT).as_posix()
    if rel.startswith("libro/") or "comer-mentiras" in existing.lower():
        return BOOK_IMAGE

    # Preserve a site-local image choice if one already exists.
    if existing:
        absolute = urljoin(BASE, existing)
        if absolute.startswith(BASE):
            return absolute

    return DEFAULT_IMAGE


def main():
    changed = 0
    skipped = []

    for path in ROOT.rglob("*.html"):
        if any(part in {".git", ".github"} for part in path.parts):
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        canonical = get_canonical(text)
        if not canonical:
            skipped.append(path.relative_to(ROOT).as_posix())
            continue

        og_title = get_meta(text, "property", "og:title")
        og_description = get_meta(text, "property", "og:description")
        og_type = get_meta(text, "property", "og:type") or "website"
        existing_image = get_meta(text, "property", "og:image")
        image = choose_image(path, existing_image)

        # Fallback values from <title> / meta description.
        if not og_title:
            m = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
            og_title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        if not og_description:
            og_description = get_meta(text, "name", "description")

        updated = text

        if og_title:
            updated = replace_or_add_meta(updated, "property", "og:title", og_title)
        if og_description:
            updated = replace_or_add_meta(updated, "property", "og:description", og_description)

        updated = replace_or_add_meta(updated, "property", "og:type", og_type)
        updated = replace_or_add_meta(updated, "property", "og:url", canonical)
        updated = replace_or_add_meta(updated, "property", "og:image", image)

        updated = replace_or_add_meta(updated, "name", "twitter:card", "summary_large_image")
        if og_title:
            updated = replace_or_add_meta(updated, "name", "twitter:title", og_title)
        if og_description:
            updated = replace_or_add_meta(updated, "name", "twitter:description", og_description)
        updated = replace_or_add_meta(updated, "name", "twitter:image", image)

        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1

    print("=" * 72)
    print("STEP 6 — OPEN GRAPH / TWITTER METADATA")
    print("=" * 72)
    print(f"HTML files modified: {changed}")
    print(f"HTML files skipped (no canonical): {len(skipped)}")
    print(f"Default image: {DEFAULT_IMAGE}")
    print(f"Book image: {BOOK_IMAGE}")

    if skipped:
        print("\nSkipped files:")
        for item in skipped:
            print(f"- {item}")


if __name__ == "__main__":
    main()
