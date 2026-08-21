#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "definitive_publication_map.md"
HTACCESS = ROOT / ".htaccess"

BEGIN = "# BEGIN NUTRECONCIENCIA FINAL ARTICLE REWRITE REDIRECTS"
END = "# END NUTRECONCIENCIA FINAL ARTICLE REWRITE REDIRECTS"

def parse_pairs():
    pairs = []
    for line in MAP.read_text(encoding="utf-8").splitlines():
        m = re.match(
            r"- `/articulos/([^/]+)/` → `https://nutreconciencia\\.com/articulos/([^/]+)/`",
            line,
        )
        if m and m.group(1) != m.group(2):
            pairs.append(m.groups())
    return sorted(set(pairs))

def main():
    pairs = parse_pairs()
    if len(pairs) < 50:
        raise RuntimeError(f"Expected ~72 mappings; found {len(pairs)}")

    existing = HTACCESS.read_text(encoding="utf-8") if HTACCESS.exists() else ""

    # Remove any previous final block.
    existing = re.sub(
        re.escape(BEGIN) + r".*?" + re.escape(END),
        "",
        existing,
        flags=re.S,
    ).strip()

    # Remove the old generic article-index rule because it can intercept
    # legacy /index.html URLs before they reach their final destination.
    existing = re.sub(
        r"RewriteCond %\{THE_REQUEST\} \\s/\+articulos/\(\[\^\\?\\s/\]\+\)/index\\\.html\(\?:\[\\?\\s\]\) \[NC\]\s*"
        r"RewriteRule \^articulos/\(\[\^/\]\+\)/index\\\.html\$ /articulos/\$1/ \[R=301,L,NE\]\s*",
        "",
        existing,
        flags=re.S,
    )

    block = [
        BEGIN,
        "RewriteEngine On",
        "",
        "# Legacy article folder URLs -> final canonical URL",
        "# /index.html variants are handled FIRST to avoid the generic index rule.",
    ]

    for old, new in pairs:
        old_re = old.replace(".", r"\.").replace("-", r"\-")
        block.append(
            f"RewriteRule ^articulos/{old_re}/index\\.html$ /articulos/{new}/ [R=301,L,NE]"
        )
        block.append(
            f"RewriteRule ^articulos/{old_re}/$ /articulos/{new}/ [R=301,L,NE]"
        )

    block += [
        "",
        END,
    ]

    # Put final article rules at the very top, before the old rules.
    final = "\n".join(block) + "\n\n" + existing.strip() + "\n"
    HTACCESS.write_text(final, encoding="utf-8")

    print("=" * 72)
    print("FINAL ARTICLE REWRITE REDIRECTS")
    print("=" * 72)
    print(f"Mappings installed: {len(pairs)}")
    print("Each mapping has:")
    print("  /old-slug/ -> /canonical/")
    print("  /old-slug/index.html -> /canonical/")
    print("Acute beetroot and iron absorption included.")
    print("The old generic article index rule is removed.")

if __name__ == "__main__":
    main()
