#!/usr/bin/env python3
"""Render the README section headings as PixelifySans images.

GitHub renders markdown headings in its own UI font, which clashes with the
pixel art. These are images instead, generated once and committed -- headings
are static, so this does not belong in CI.

A PNG cannot follow the reader's theme, so each heading is rendered twice and
the README picks between them with <picture> + prefers-color-scheme.

Usage: python3 .github/scripts/headings.py
"""

import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pngcrop import crop_to_content  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
FONT = ROOT / "assets" / "fonts" / "PixelifySans-Medium.ttf"
OUT = ROOT / "assets" / "headings"

# Ink on light backgrounds, soft pink on dark -- both sit on transparent.
VARIANTS = {"light": "#5F78A7", "dark": "#FFB6C1"}

FONT_SIZE = 30
SCALE = 2  # rendered at 2x so the pixel grid stays crisp on high-DPI screens
WINDOW = (900, 200)  # comfortably larger than any heading; cropped back after

HEADINGS = {
    "currently": "CURRENTLY",
    "tools": "TOOLS AND TECH",
    "stats": "GITHUB STATS",
    "city": "MY CONTRIBUTION CITY",
    "dsa": "DSA AND CP",
    "built": "THINGS I'VE BUILT",
    "hello": "SAY HELLO",
}

CHROME_CANDIDATES = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
]

PAGE = """<!doctype html>
<meta charset="utf-8">
<style>
  @font-face {{ font-family: PX; src: url('file://{font}'); }}
  html, body {{ margin: 0; padding: 0; background: transparent; }}
  span {{
    font-family: PX;
    font-size: {size}px;
    color: {color};
    line-height: 1.35;
    white-space: pre;
    display: inline-block;
    padding: 4px 2px;
  }}
</style>
<body><span>{text}</span></body>
"""


def find_chrome():
    for path in CHROME_CANDIDATES:
        if pathlib.Path(path).exists():
            return path
    found = shutil.which("chromium") or shutil.which("google-chrome")
    if found:
        return found
    sys.exit("no Chromium found; cannot render headings")


def render(chrome, text, color, destination):
    # Chromium renders nothing in a viewport sized tightly around the text, so
    # shoot into a generously large one and crop back to the glyphs afterwards.
    with tempfile.TemporaryDirectory() as tmp:
        page = pathlib.Path(tmp) / "h.html"
        page.write_text(PAGE.format(font=FONT, size=FONT_SIZE, color=color, text=text))
        shot = pathlib.Path(tmp) / "shot.png"
        subprocess.run(
            [
                chrome,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--default-background-color=00000000",
                # Without this the screenshot can fire while @font-face is
                # still loading, producing invisible text.
                "--virtual-time-budget=3000",
                f"--force-device-scale-factor={SCALE}",
                f"--window-size={WINDOW[0]},{WINDOW[1]}",
                f"--screenshot={shot}",
                f"file://{page}",
            ],
            check=True,
            capture_output=True,
        )
        destination.write_bytes(crop_to_content(shot.read_bytes()))


def main():
    if not FONT.exists():
        sys.exit(f"missing font: {FONT}")

    chrome = find_chrome()
    OUT.mkdir(parents=True, exist_ok=True)

    for slug, text in HEADINGS.items():
        for variant, color in VARIANTS.items():
            destination = OUT / f"{slug}-{variant}.png"
            render(chrome, text, color, destination)
            print(f"{destination.relative_to(ROOT)}  {destination.stat().st_size:,} bytes")

    print(f"\n{len(HEADINGS) * len(VARIANTS)} heading images written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
