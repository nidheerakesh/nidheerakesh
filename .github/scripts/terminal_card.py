#!/usr/bin/env python3
"""Render assets/terminal-card.svg: a neofetch-style profile card.

Pixel initials on the left, a labelled readout on the right, inside a terminal
window. The numbers come from the caches the other cards already write, so the
card ages with the profile instead of going stale.

Never fails the workflow: missing caches just drop their rows.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from card import LAVENDER, PINK, THEMES, esc, truncate  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / ".github" / "data"
OUT = ROOT / "assets" / "terminal-card.svg"

NAME = "Nidhi Rakesh"
SUBTITLE = "CS undergrad, IIIT Kottayam"
PROMPT = "nidhi@github:~"
INITIALS = "NR"

WIDTH, HEIGHT = 920, 348
BAR = 46            # title bar height
ART_X, ART_BLOCK = 60, 20
TEXT_X = 430
LABEL_W = 108

# Rows that are not derived from data. Edit these freely.
STATIC = [
    ("skills", "Python, PyTorch, FastAPI, React, TypeScript"),
    ("building", "FoundIt, loom, sentinelgraph"),
    ("into", "quantum computing, graph ML, healthcare AI"),
]

# 5x7 pixel glyphs, enough for the initials.
GLYPHS = {
    "N": ["10001", "11001", "11001", "10101", "10011", "10011", "10001"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
}

ACCENTS = {"light": ("#F09BB4", "#9FB6DE"), "dark": (PINK, "#B8CAE8")}


def load(name):
    try:
        return json.loads((DATA / name).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def rows():
    """Static rows plus whatever the caches can fill in."""
    out = list(STATIC)

    oss = load("oss.json")
    if oss.get("top"):
        names = [e["repo"].split("/")[-1] for e in oss["top"][:3]]
        merged = oss.get("merged")
        tail = f" ({merged} merged)" if merged else ""
        out.insert(2, ("open source", ", ".join(names) + tail))

    stats = load("stats.json")
    solved = sum(
        v["solved"] for v in stats.values()
        if isinstance(v, dict) and isinstance(v.get("solved"), int)
    )
    if solved:
        out.append(("solved", f"{solved:,} problems across three judges"))

    github = load("github.json")
    if github.get("contributions"):
        streak = github.get("streak")
        extra = f", {streak} day streak" if streak else ""
        out.append(("this year", f"{github['contributions']:,} contributions{extra}"))

    return out


def art(theme):
    """Chunky pixel initials, alternating the two accents."""
    pink, blue = ACCENTS[theme]
    cells = []
    y0 = BAR + 64
    for index, char in enumerate(INITIALS):
        glyph = GLYPHS.get(char)
        if not glyph:
            continue
        x0 = ART_X + index * (6 * ART_BLOCK)
        for r, line in enumerate(glyph):
            for c, bit in enumerate(line):
                if bit != "1":
                    continue
                colour = pink if (r + c + index) % 2 == 0 else blue
                cells.append(
                    f'  <rect x="{x0 + c * ART_BLOCK}" y="{y0 + r * ART_BLOCK}" '
                    f'width="{ART_BLOCK - 3}" height="{ART_BLOCK - 3}" rx="3" fill="{colour}"/>'
                )
    # a small heart under the initials
    heart = ["01010", "11111", "11111", "01110", "00100"]
    hx, hy, hb = ART_X + 118, y0 + 7 * ART_BLOCK + 16, 8
    for r, line in enumerate(heart):
        for c, bit in enumerate(line):
            if bit == "1":
                cells.append(
                    f'  <rect x="{hx + c * hb}" y="{hy + r * hb}" width="{hb - 2}" '
                    f'height="{hb - 2}" rx="2" fill="{pink}" opacity=".85"/>'
                )
    return "\n".join(cells)


def render(theme="light"):
    palette = THEMES[theme]
    pink, blue = ACCENTS[theme]
    bar_fill = "#F3E8DC" if theme == "light" else "#272330"
    ink, text = palette["ink"], palette["text"]

    body = [art(theme)]
    body.append(
        f'  <text x="{TEXT_X}" y="{BAR + 48}" class="who">{esc(PROMPT)}</text>'
        f'\n  <line x1="{TEXT_X}" y1="{BAR + 62}" x2="{WIDTH - 60}" y2="{BAR + 62}" '
        f'stroke="{palette["border"]}" stroke-width="1"/>'
        f'\n  <text x="{TEXT_X}" y="{BAR + 92}" class="name">{esc(NAME)}</text>'
        f'\n  <text x="{TEXT_X}" y="{BAR + 116}" class="sub">{esc(SUBTITLE)}</text>'
    )

    y = BAR + 156
    for label, value in rows():
        body.append(
            f'  <text x="{TEXT_X}" y="{y}" class="key">{esc(label)}</text>'
            f'\n  <text x="{TEXT_X + LABEL_W}" y="{y}" class="val">'
            f'{esc(truncate(value, 52))}</text>'
        )
        y += 28

    height = max(HEIGHT, y + 24)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{esc(NAME)}, {esc(SUBTITLE)}">
  <style>
    .mono {{ font-family: ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace; }}
    .who {{ font: 600 15px ui-monospace, Menlo, Consolas, monospace; fill: {blue}; }}
    .name {{ font: 600 19px ui-monospace, Menlo, Consolas, monospace; fill: {ink}; }}
    .sub {{ font: 400 13px ui-monospace, Menlo, Consolas, monospace; fill: {text}; opacity: .75; }}
    .key {{ font: 600 13px ui-monospace, Menlo, Consolas, monospace; fill: {pink}; }}
    .val {{ font: 400 13px ui-monospace, Menlo, Consolas, monospace; fill: {text}; }}
    .ttl {{ font: 400 12px ui-monospace, Menlo, Consolas, monospace; fill: {text}; opacity: .7; text-anchor: middle; }}
  </style>
  <rect x="1" y="1" width="{WIDTH - 2}" height="{height - 2}" rx="16" fill="{palette['bg']}" stroke="{palette['border']}" stroke-width="2"/>
  <path d="M1 17 a16 16 0 0 1 16 -16 h{WIDTH - 34} a16 16 0 0 1 16 16 v{BAR - 16} h-{WIDTH - 2} Z" fill="{bar_fill}"/>
  <line x1="1" y1="{BAR}" x2="{WIDTH - 1}" y2="{BAR}" stroke="{palette['border']}" stroke-width="1"/>
  <circle cx="30" cy="{BAR // 2}" r="6" fill="{pink}"/>
  <circle cx="50" cy="{BAR // 2}" r="6" fill="{LAVENDER if theme == 'light' else '#6E6482'}"/>
  <circle cx="70" cy="{BAR // 2}" r="6" fill="{blue}"/>
  <text x="{WIDTH // 2}" y="{BAR // 2 + 4}" class="ttl">{esc(PROMPT)}</text>
  <line x1="{TEXT_X - 40}" y1="{BAR + 28}" x2="{TEXT_X - 40}" y2="{height - 28}" stroke="{palette['border']}" stroke-width="1"/>
{chr(10).join(body)}
</svg>
"""


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render("light"))
    OUT.with_name("terminal-card-dark.svg").write_text(render("dark"))
    print(f"wrote {OUT.name} and its dark variant ({len(rows())} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
