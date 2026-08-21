#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "assets" / "styles.css"

FONT_IMPORT = (
    '@import url("https://fonts.googleapis.com/css2?'
    'family=Inter:wght@400;500;600;700;800&'
    'family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700&'
    'display=swap");\n\n'
)

def main():
    if not CSS.exists():
        raise FileNotFoundError("assets/styles.css not found")

    text = CSS.read_text(encoding="utf-8", errors="ignore")
    original = text

    # Load the intended fonts once.
    if "fonts.googleapis.com/css2?family=Inter" not in text:
        text = FONT_IMPORT + text

    # Make the global design tokens explicit.
    text = re.sub(
        r'--serif:Georgia,"Times New Roman",serif;',
        '--serif:"Source Serif 4",Georgia,"Times New Roman",serif;',
        text,
        count=1,
    )
    text = re.sub(
        r'--sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;',
        '--sans:"Inter",ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;',
        text,
        count=1,
    )

    # Replace direct Georgia declarations in editorial/content components.
    # Deliberately exclude media/logo selectors, which are visual brand marks.
    replacements = [
        (r'font-family:Georgia,"Times New Roman",serif;', 'font-family:var(--serif);'),
        (r'font-family:Georgia,serif;', 'font-family:var(--serif);'),
        (r'font:500 21px/1\.12 Georgia,serif;', 'font:500 21px/1.12 var(--serif);'),
        (r'font:500 36px/1\.04 Georgia,serif;', 'font:500 36px/1.04 var(--serif);'),
        (r'font:500 27px/1\.08 Georgia,serif;', 'font:500 27px/1.08 var(--serif);'),
        (r'font:500 23px/1\.08 Georgia,serif;', 'font:500 23px/1.08 var(--serif);'),
        (r'font:500 25px/1\.08 Georgia,serif;', 'font:500 25px/1.08 var(--serif);'),
        (r'font:500 24px/1\.45 Georgia,serif;', 'font:500 24px/1.45 var(--serif);'),
        (r'font:500 22px/1\.45 Georgia,serif;', 'font:500 22px/1.45 var(--serif);'),
        (r'font:500 20px/1\.4 Georgia,serif;', 'font:500 20px/1.4 var(--serif);'),
        (r'font:500 20px/1\.38 Georgia,serif;', 'font:500 20px/1.38 var(--serif);'),
        (r'font:500 25px/1\.42 Georgia,serif;', 'font:500 25px/1.42 var(--serif);'),
    ]

    changed = 0
    for pattern, replacement in replacements:
        text, n = re.subn(pattern, replacement, text)
        changed += n

    if text == original:
        print("No CSS changes needed.")
        return

    CSS.write_text(text, encoding="utf-8")

    remaining_editorial = [
        line for line in text.splitlines()
        if "Georgia" in line and not any(
            marker in line
            for marker in (
                ".logo-text.",
                ".masthead-item .logo",
                ".news-masthead .logo",
                ".media-logo",
                ".brand-serif",
                ".journal-brand",
                ".paper-cover-journal",
                ".paper-cover-title",
                ".study-hero h1",
            )
        )
    ]

    print("=" * 72)
    print("STEP 10 — GLOBAL TYPOGRAPHY")
    print("=" * 72)
    print("Font import added:", "fonts.googleapis.com/css2?family=Inter" in text)
    print("Serif token: Source Serif 4")
    print("Sans token: Inter")
    print("Direct editorial Georgia declarations replaced:", changed)
    print("Media/logo Georgia declarations intentionally preserved.")
    print("styles.css updated.")
    if remaining_editorial:
        print("Remaining Georgia-containing editorial lines:")
        for line in remaining_editorial[:20]:
            print(" -", line[:220])
    else:
        print("No unintended editorial Georgia declarations remain.")

if __name__ == "__main__":
    main()
