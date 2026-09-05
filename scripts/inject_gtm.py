from pathlib import Path
import re

GTM_ID = "GTM-KVG76QVX"
ROOT = Path(".")

HEAD_SNIPPET = f"""<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{GTM_ID}');</script>
<!-- End Google Tag Manager -->"""

BODY_SNIPPET = f"""<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={GTM_ID}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""


def inject_into_html(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")

    # No tocar una página que ya tenga este contenedor.
    if GTM_ID in text:
        return False

    original = text

    # Insertar inmediatamente después de <head>
    text, head_count = re.subn(
        r"(<head\b[^>]*>)",
        r"\1\n" + HEAD_SNIPPET,
        text,
        count=1,
        flags=re.IGNORECASE,
    )

    if head_count != 1:
        print(f"[SKIP] No se encontró <head>: {path}")
        return False

    # Insertar inmediatamente después de <body>
    text, body_count = re.subn(
        r"(<body\b[^>]*>)",
        r"\1\n" + BODY_SNIPPET,
        text,
        count=1,
        flags=re.IGNORECASE,
    )

    if body_count != 1:
        print(f"[SKIP] No se encontró <body>: {path}")
        return False

    if text == original:
        return False

    path.write_text(text, encoding="utf-8")
    return True


def main():
    html_files = sorted(ROOT.rglob("*.html"))

    changed = 0
    skipped_existing = 0

    for path in html_files:
        # Ignorar directorios de git si aparecieran en el workspace.
        if ".git" in path.parts:
            continue

        content = path.read_text(encoding="utf-8", errors="ignore")

        if GTM_ID in content:
            skipped_existing += 1
            print(f"[EXISTS] {path}")
            continue

        if inject_into_html(path):
            changed += 1
            print(f"[ADDED] {path}")

    print()
    print(f"Páginas HTML encontradas: {len(html_files)}")
    print(f"Páginas actualizadas: {changed}")
    print(f"Páginas que ya tenían GTM: {skipped_existing}")


if __name__ == "__main__":
    main()
