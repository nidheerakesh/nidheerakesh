#!/usr/bin/env python3
"""Render assets/city-card.svg: an isometric contribution calendar.

Replaces yoshi389111/github-profile-3d-contrib. That action always drew a full
year, so a calendar whose activity started partway through showed a long run of
bare grid, and its donut and radar used GitHub's own language colours, which
clashed with everything else here.

This starts at the first week that has any activity, so the city is always
full, and sizes the tiles to the canvas so a short history fills the frame just
as a long one does.

Reads .github/data/github.json, written by github_card.py, so it needs no
network of its own. Never fails the workflow.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from card import (  # noqa: E402
    RAMP, THEMES,
    esc, frame, num, truncate,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / ".github" / "data" / "github.json"
OUT = ROOT / "assets" / "city-card.svg"

MAX_WIDTH = 900
MIN_WIDTH = 740  # donut + two legend columns + the totals, without colliding
PAD = 34
ROWS = 7  # days per week
MAX_BAR = 46  # tallest column, in pixels
FOOTER = 92  # room under the grid for the donut and totals
DENSITY = 0.7  # a window is "full" when this share of weeks has activity
MIN_WEEKS = 12  # never shrink below this, even for a quiet account

# Four intensity steps, as GitHub's calendar uses, lightest first.
LEVELS = {
    "light": ["#F0E7DA", "#FFE0E8", "#FFC3D0", "#F79BB0", "#E07D9A"],
    "dark": ["#2A2731", "#4A3340", "#6E4454", "#A85F77", "#FFB6C1"],
}
# Side faces are shaded so the cubes read as solid.
SHADE = {"left": 0.72, "right": 0.86}


def shade(hex_color, factor):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % (
        int(r * factor), int(g * factor), int(b * factor)
    )


def trim(days):
    """Pick the longest recent window that still looks busy.

    Dropping only leading *empty* weeks is not enough: a single contribution in
    week one followed by months of nothing keeps the whole year in frame, which
    is the bare-grid look this card exists to avoid. So take the earliest start
    whose remaining weeks are at least DENSITY active, which keeps as much
    history as possible without the sparse run-up.
    """
    weeks = [days[i : i + ROWS] for i in range(0, len(days), ROWS)]
    totals = [sum(day["c"] for day in week) for week in weeks]
    if not any(totals):
        return days[-ROWS * MIN_WEEKS :]  # nothing yet: show a short window

    start = None
    for candidate in range(len(totals)):
        window = totals[candidate:]
        if len(window) < MIN_WEEKS:
            break
        if sum(1 for total in window if total) / len(window) >= DENSITY:
            start = candidate
            break
    if start is None:
        start = max(0, len(totals) - MIN_WEEKS)

    while start < len(totals) - 1 and not totals[start]:
        start += 1  # never open on an empty week
    return [day for week in weeks[start:] for day in week]


def level(count, peak):
    if count <= 0:
        return 0
    if peak <= 1:
        return 4
    return min(4, 1 + int(3 * (count - 1) / max(1, peak - 1)))


def render(stats, theme="light"):
    palette = THEMES[theme]
    ramp = LEVELS[theme]
    days = trim(stats.get("calendar") or [])
    weeks = max(1, (len(days) + ROWS - 1) // ROWS)

    # Tile size follows the week count so a short history fills the frame, then
    # the canvas shrinks to the strip rather than leaving dead space beside it.
    span = weeks + ROWS - 1
    tile_w = max(10, min(40, (MAX_WIDTH - 2 * PAD) * 2 // (span + 1)))
    tile_h = tile_w // 2

    strip_w = span * tile_w // 2 + tile_w
    width = max(MIN_WIDTH, min(MAX_WIDTH, strip_w + 2 * PAD))
    origin_x = (width - strip_w) // 2 + (ROWS - 1) * tile_w // 2 + tile_w // 2
    origin_y = 76 + MAX_BAR
    height = origin_y + span * tile_h // 2 + FOOTER

    peak = max((day["c"] for day in days), default=0)
    body = []

    # Painter's order: back to front is increasing (week + weekday).
    cells = []
    for index, day in enumerate(days):
        week, weekday = divmod(index, ROWS)
        cells.append((week + weekday, week, weekday, day))
    cells.sort(key=lambda c: (c[0], c[1]))

    for _, week, weekday, day in cells:
        count = day["c"]
        tier = level(count, peak)
        colour = ramp[tier]
        bar = round(MAX_BAR * count / peak) if peak and count else 0

        cx = origin_x + (week - weekday) * tile_w // 2
        cy = origin_y + (week + weekday) * tile_h // 2 - bar
        half_w, half_h = tile_w // 2, tile_h // 2

        if bar:
            body.append(
                f'  <path d="M{cx - half_w} {cy} L{cx} {cy + half_h} '
                f'L{cx} {cy + half_h + bar} L{cx - half_w} {cy + bar} Z" '
                f'fill="{shade(colour, SHADE["left"])}"/>'
            )
            body.append(
                f'  <path d="M{cx + half_w} {cy} L{cx} {cy + half_h} '
                f'L{cx} {cy + half_h + bar} L{cx + half_w} {cy + bar} Z" '
                f'fill="{shade(colour, SHADE["right"])}"/>'
            )
        body.append(
            f'  <path d="M{cx} {cy - half_h} L{cx + half_w} {cy} '
            f'L{cx} {cy + half_h} L{cx - half_w} {cy} Z" fill="{colour}"'
            + (f' stroke="{palette["bg"]}" stroke-width=".5"' if not bar else "")
            + "/>"
        )

    body.append(donut(stats, width, height, theme))
    body.append(totals(stats, width, height))

    return frame(
        width, height, "contribution city",
        f"{days[0]['d']} → {days[-1]['d']}" if days else "",
        "\n".join(body) + "\n",
        theme,
    )


def donut(stats, width, height, theme):
    """Language ring, in the same pastels as the rest of the card."""
    languages = stats.get("language_repos") or {}
    total = sum(languages.values())
    cx, cy, radius = PAD + 54, height - 50, 32
    circumference = 2 * 3.14159 * radius

    parts = [
        f'  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
        f'stroke="{THEMES[theme]["pale"]}" stroke-width="14"/>'
    ]
    offset = 0.0
    for index, (name, count) in enumerate(languages.items()):
        length = circumference * count / total if total else 0
        parts.append(
            f'  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
            f'stroke="{RAMP[index % len(RAMP)]}" stroke-width="14" '
            f'stroke-dasharray="{length:.1f} {circumference - length:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += length

    x = cx + radius + 22
    y = cy - 24
    for index, name in enumerate(languages):
        parts.append(
            f'  <circle cx="{x + 5}" cy="{y - 4}" r="4" fill="{RAMP[index % len(RAMP)]}"/>'
            f'<text x="{x + 16}" y="{y}" class="s">{esc(truncate(name, 12))}</text>'
        )
        y += 17
        if index == 2:  # second column once three are listed
            x += 118
            y = cy - 24
    return "\n".join(parts)


def totals(stats, width, height):
    y = height - 38
    x = width - PAD
    pieces = [
        f'  <text x="{x}" y="{y}" class="val" font-size="15">'
        f'{num(stats.get("contributions"))}</text>',
        f'  <text x="{x}" y="{y + 16}" class="cap" text-anchor="end">CONTRIBUTIONS</text>',
        f'  <text x="{x - 150}" y="{y}" class="val" font-size="15">'
        f'{num(stats.get("stars"))}</text>',
        f'  <text x="{x - 150}" y="{y + 16}" class="cap" text-anchor="end">STARS</text>',
        f'  <text x="{x - 260}" y="{y}" class="val" font-size="15">'
        f'{num(stats.get("forks"))}</text>',
        f'  <text x="{x - 260}" y="{y + 16}" class="cap" text-anchor="end">FORKS</text>',
    ]
    return "\n".join(pieces)


def main():
    try:
        stats = json.loads(CACHE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"no usable {CACHE.name} ({type(exc).__name__}); skipping the city")
        return 0

    if not stats.get("calendar"):
        print("no calendar in the cache yet; skipping the city this run")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(stats, "light"))
    OUT.with_name("city-card-dark.svg").write_text(render(stats, "dark"))
    days = trim(stats["calendar"])
    print(
        f"wrote {OUT.name} and its dark variant "
        f"({len(days) // ROWS} weeks from {days[0]['d']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
