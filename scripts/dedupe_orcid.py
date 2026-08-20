#!/usr/bin/env python3
"""
Clean up duplicate ORCID-managed article folders.

- Only folders containing orcid.json are considered.
- Groups are built using DOI, PMID, ORCID work ID and normalized title.
- One canonical folder is retained.
- Duplicate folders are converted into lightweight redirect/noindex pages
  pointing to the canonical URL instead of being deleted.
"""
from __future__ import annotations
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"
BASE_URL = "https://nutreconciencia.com/articulos"


def normalize_title_key(value: str) -> str:
    value = html.unescape(value or "").lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def meta(folder: Path) -> dict:
    f = folder / "orcid.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def identity(m: dict) -> tuple[str, str, str, str]:
    return (
        (m.get("doi") or "").strip().lower(),
        str(m.get("pmid") or "").strip(),
        str(m.get("orcid_work_id") or m.get("put_code") or m.get("orcid_put_code") or "").strip(),
        normalize_title_key(m.get("title") or ""),
    )


def choose_canonical(folders: list[Path], metas: dict[Path, dict]) -> Path:
    # Prefer the folder whose slug equals the generated slug of its own title;
    # otherwise choose the lexicographically shortest name for stability.
    scored = []
    for f in folders:
        title = metas[f].get("title", "")
        slug_base = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip().lower()
        slug_base = re.sub(r"[\s_-]+", "-", slug_base)
        slug_base = re.sub(r"[^a-z0-9-]", "", slug_base)[:100].strip("-") or "paper"
        score = (
            0 if f.name == slug_base else 1,
            len(f.name),
            f.name,
        )
        scored.append((score, f))
    return sorted(scored, key=lambda x: x[0])[0][1]


def redirect_page(canonical: Path, duplicate: Path) -> str:
    target = f"{BASE_URL}/{canonical.name}/"
    title = html.escape(canonical.name)
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0;url={target}">
<title>Redirigiendo…</title>
</head>
<body>
<p>Esta publicación se ha consolidado en <a href="{target}">{title}</a>.</p>
</body>
</html>
"""


def main() -> None:
    ART.mkdir(exist_ok=True)
    groups: dict[tuple, list[Path]] = {}

    for folder in sorted(ART.iterdir()):
        if not folder.is_dir():
            continue
        m = meta(folder)
        if not m:
            continue
        ident = identity(m)

        # Skip entries without any usable stable identifier.
        if not any(ident):
            continue

        # Use each identity independently and merge later.
        for key_index, value in enumerate(ident):
            if not value:
                continue
            groups.setdefault((key_index, value), []).append(folder)

    # Merge overlapping identity groups.
    parent: dict[Path, Path] = {}

    def find(x: Path) -> Path:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: Path, b: Path) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for folders in groups.values():
        if len(folders) > 1:
            first = folders[0]
            for other in folders[1:]:
                union(first, other)

    components: dict[Path, list[Path]] = {}
    for folder in parent:
        components.setdefault(find(folder), []).append(folder)

    changed = 0
    for folders in components.values():
        if len(folders) < 2:
            continue
        metas = {f: meta(f) for f in folders}
        canonical = choose_canonical(folders, metas)
        for duplicate in folders:
            if duplicate == canonical:
                continue
            (duplicate / "index.html").write_text(
                redirect_page(canonical, duplicate), encoding="utf-8"
            )
            changed += 1
            print(f"Redirect: {duplicate.name} -> {canonical.name}")

    print(f"Duplicate cleanup complete. Redirected {changed} duplicate folders.")


if __name__ == "__main__":
    main()
