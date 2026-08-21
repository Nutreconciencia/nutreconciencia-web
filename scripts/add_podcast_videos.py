#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "podcasts" / "index.html"

VIDEOS = [
    "jKE1a4uyZCQ",
    "LoQOe_mDVm8",
    "ep0oSj3-RqA",
    "IGBHtFiPXOY",
    "eu0vZQ81IvU",
    "2-0vdBPhaWA",
    "_Kr7a3Aptyc",
    "j0KFL6aICBY",
]

UA = "NutreconcienciaWeb/1.0 (https://nutreconciencia.com/)"

def fetch_oembed(video_id: str) -> tuple[str, str]:
    url = (
        "https://www.youtube.com/oembed?url="
        + urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}", safe="")
        + "&format=json"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data.get("title", "").strip(), data.get("author_name", "").strip()

def existing_video_ids(text: str) -> set[str]:
    return set(re.findall(
        r'youtube\.com/(?:watch\?v=|embed/)([A-Za-z0-9_-]{11})',
        text,
        flags=re.I,
    ))

def card(video_id: str, title: str, channel: str) -> str:
    if not title:
        title = "Vídeo en YouTube"
    if not channel:
        channel = "YouTube"

    safe_title = escape(title)
    safe_channel = escape(channel)

    return (
        f'<a class="podcast-card" '
        f'href="https://www.youtube.com/watch?v={video_id}" '
        f'target="_blank" rel="noopener">'
        f'<div class="video-thumb">'
        f'<img src="https://img.youtube.com/vi/{video_id}/maxresdefault.jpg" '
        f'alt="{safe_title}">'
        f'<span class="play-dot">▶</span>'
        f'</div>'
        f'<div class="copy">'
        f'<div class="podcast-meta">{safe_channel} · YouTube</div>'
        f'<h4>{safe_title}</h4>'
        f'<p>Entrevista y divulgación sobre nutrición, ciencia, salud y evidencia.</p>'
        f'</div></a>'
    )

def main():
    if not PAGE.exists():
        raise FileNotFoundError("podcasts/index.html not found")

    text = PAGE.read_text(encoding="utf-8", errors="ignore")

    grid = re.search(
        r'(<div\s+class=["\']podcast-grid["\'][^>]*>)(.*?)(</div>\s*</div>\s*</section>)',
        text,
        flags=re.I | re.S,
    )
    if not grid:
        raise RuntimeError("Could not locate .podcast-grid")

    inner = grid.group(2)
    existing = existing_video_ids(text)

    pending = [vid for vid in VIDEOS if vid not in existing]

    if not pending:
        print("=" * 72)
        print("PODCAST PAGE — NO NEW VIDEOS")
        print("=" * 72)
        print("All 8 supplied YouTube videos are already present.")
        return

    cards = []
    failures = []

    for video_id in pending:
        try:
            title, channel = fetch_oembed(video_id)
            cards.append(card(video_id, title, channel))
            print(f" - {video_id} | {title or 'NO TITLE'} | {channel or 'NO CHANNEL'}")
        except Exception as exc:
            failures.append((video_id, str(exc)))
            cards.append(card(video_id, "", "YouTube"))
            print(f" - {video_id} | oEmbed failed; fallback card created: {exc}")

    new_inner = inner.rstrip() + "\n" + "\n".join(cards) + "\n"
    updated = text[:grid.start(2)] + new_inner + text[grid.end(2):]

    # Ensure all 8 URLs are present exactly once in the final page.
    for video_id in VIDEOS:
        count = updated.count(f'youtube.com/watch?v={video_id}')
        if count != 1:
            raise RuntimeError(
                f"Video {video_id} occurs {count} times after update; refusing to write."
            )

    PAGE.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("PODCAST PAGE — 8 VIDEOS ADDED")
    print("=" * 72)
    print(f"New cards added: {len(pending)}")
    print("Existing cards preserved.")
    print(f"oEmbed fallbacks: {len(failures)}")
    print("Only podcasts/index.html was modified.")

if __name__ == "__main__":
    main()
