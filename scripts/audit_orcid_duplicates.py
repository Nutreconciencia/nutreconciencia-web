#!/usr/bin/env python3
"""
Audit ORCID-managed article folders for duplicates without changing any files.

Reports groups of folders sharing a DOI, PMID, ORCID work ID, or normalized title.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "articulos"


def normalize_title(value: str) -> str:
    value = html.unescape(value or "").lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def load_meta(folder: Path) -> dict:
    f = folder / "orcid.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def identities(meta: dict) -> dict[str, str]:
    return {
        "doi": (meta.get("doi") or "").strip().lower(),
        "pmid": str(meta.get("pmid") or "").strip(),
        "orcid_work_id": str(
            meta.get("orcid_work_id")
            or meta.get("put_code")
            or meta.get("orcid_put_code")
            or ""
        ).strip(),
        "title": normalize_title(meta.get("title") or ""),
    }


def main() -> None:
    buckets: dict[tuple[str, str], set[Path]] = {}

    for folder in sorted(ART.iterdir()):
        if not folder.is_dir():
            continue
        meta = load_meta(folder)
        if not meta:
            continue
        for key, value in identities(meta).items():
            if value:
                buckets.setdefault((key, value), set()).add(folder)

    duplicate_groups: list[set[Path]] = []
    for folders in buckets.values():
        if len(folders) > 1:
            duplicate_groups.append(folders)

    # Merge overlapping groups so one publication is reported once.
    merged: list[set[Path]] = []
    for group in duplicate_groups:
        overlaps = [g for g in merged if g & group]
        if not overlaps:
            merged.append(set(group))
        else:
            combined = set(group)
            for g in overlaps:
                combined |= g
                merged.remove(g)
            merged.append(combined)

    merged.sort(key=lambda g: sorted(p.name for p in g)[0])

    print(f"Duplicate groups found: {len(merged)}")
    total = 0
    for i, group in enumerate(merged, 1):
        names = sorted(p.name for p in group)
        total += len(names) - 1
        print(f"\nGROUP {i} ({len(names)} folders)")
        for name in names:
            meta = load_meta(ART / name)
            print(
                f"- {name} | "
                f"DOI={meta.get('doi','')} | "
                f"PMID={meta.get('pmid','')} | "
                f"Title={meta.get('title','')}"
            )

    print(f"\nDuplicate folders beyond canonical copies: {total}")


if __name__ == "__main__":
    main()
