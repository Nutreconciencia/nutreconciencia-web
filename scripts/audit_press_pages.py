#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "prensa"
OUT_CSV = ROOT / "press_pages_audit.csv"
OUT_MD = ROOT / "press_pages_audit.md"


def clean(v: str) -> str:
    v = html.unescape(v or "")
    return re.sub(r"\s+", " ", v).strip()


def extract(pattern: str, text: str) -> str:
    m = re.search(pattern, text, flags=re.I | re.S)
    return clean(m.group(1)) if m else ""


def meta(text: str, key_attr: str, key_value: str) -> str:
    for m in re.finditer(r"<meta\b([^>]*)>", text, flags=re.I | re.S):
        attrs = m.group(1)
        km = re.search(
            rf'\b{re.escape(key_attr)}\s*=\s*(["\'])(.*?)\1',
            attrs,
            flags=re.I | re.S,
        )
        if not km or km.group(2).lower() != key_value.lower():
            continue
        cm = re.search(
            r'\bcontent\s*=\s*(["\'])(.*?)\1',
            attrs,
            flags=re.I | re.S,
        )
        return clean(cm.group(2)) if cm else ""
    return ""


def canonical(text: str) -> str:
    return extract(
        r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
        text,
    )


def main() -> None:
    if not PRESS.exists():
        raise FileNotFoundError("No existe la carpeta prensa/")

    rows = []

    for folder in sorted(PRESS.iterdir()):
        if not folder.is_dir():
            continue

        page = folder / "index.html"
        if not page.exists():
            continue

        text = page.read_text(encoding="utf-8", errors="ignore")

        title = extract(r"<h1[^>]*>(.*?)</h1>", text) or extract(r"<title[^>]*>(.*?)</title>", text)
        description = extract(r'<meta\b[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', text)

        # Try common article/news metadata patterns.
        date = extract(
            r'(?:datePublished|dateModified)["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            text,
        )
        original_url = extract(
            r'(?:href|url)=["\'](https?://[^"\']+)["\']',
            text,
        )

        rows.append({
            "slug": folder.name,
            "title": title,
            "date": date,
            "original_url_candidate": original_url,
            "canonical": canonical(text),
            "og_title": meta(text, "property", "og:title"),
            "og_description": meta(text, "property", "og:description"),
            "og_image": meta(text, "property", "og:image"),
            "twitter_image": meta(text, "name", "twitter:image"),
        })

    fields = list(rows[0].keys()) if rows else [
        "slug", "title", "date", "original_url_candidate", "canonical",
        "og_title", "og_description", "og_image", "twitter_image"
    ]

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    md = [
        "# Press pages audit",
        "",
        f"- Press pages with index.html: **{len(rows)}**",
        "",
        "| Slug | Título | Fecha | Canonical | OG image |",
        "|---|---|---|---|---|",
    ]

    for r in rows:
        md.append(
            f"| `{r['slug']}` | {r['title']} | {r['date']} | "
            f"`{r['canonical']}` | `{r['og_image']}` |"
        )

    md.append("")
    md.append("## Details")
    md.append("")
    for r in rows:
        md += [
            f"### {r['slug']}",
            f"- Título: {r['title']}",
            f"- Fecha: {r['date']}",
            f"- URL original candidata: {r['original_url_candidate']}",
            f"- Canonical: {r['canonical']}",
            f"- og:title: {r['og_title']}",
            f"- og:description: {r['og_description']}",
            f"- og:image: {r['og_image']}",
            f"- twitter:image: {r['twitter_image']}",
            "",
        ]

    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("=" * 72)
    print("STEP 8 — PRESS PAGES AUDIT")
    print("=" * 72)
    print(f"Press pages with index.html: {len(rows)}")
    print(f"Created: {OUT_MD.name}")
    print(f"Created: {OUT_CSV.name}")
    print("READ-ONLY — no press pages were modified.")


if __name__ == "__main__":
    main()
