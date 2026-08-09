#!/usr/bin/env python3
"""Shared palette, SVG scaffolding and fetch helpers for the generated cards.

Every card in this repo is a plain SVG committed to the tree, because that is
the only thing that reliably renders in a GitHub README -- the third-party
image services this replaced were permanently over quota.
"""

import json
import urllib.request

# Palette, sampled from the pixel art in assets/.
CREAM = "#FDF6EC"
PINK = "#FFB6C1"
PINK_SOFT = "#FFD9E0"
LAVENDER = "#E6E6FA"
INK = "#5F78A7"
PALE = "#E7EEF8"
BROWN = "#8B5E4B"

# Colour ramp for anything needing several distinguishable pastels (languages,
# platform rows). Ordered so neighbours stay distinguishable.
RAMP = [PINK, "#B8CAE8", LAVENDER, "#F7C9A8", "#C7E3D4", "#D9C2E9"]

UA = "Mozilla/5.0 (compatible; profile-readme-card/1.0; +https://github.com/nidheerakesh)"

STYLE = f"""    .t {{ font: 600 17px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; }}
    .s {{ font: 400 11px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .75; }}
    .big {{ font: 700 38px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; }}
    .mid {{ font: 700 20px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; text-anchor: middle; }}
    .cap {{ font: 400 9px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .7; letter-spacing: .8px; }}
    .capm {{ font: 400 9px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .7; letter-spacing: .8px; text-anchor: middle; }}
    .lbl {{ font: 500 12px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; }}
    .val {{ font: 600 12px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; text-anchor: end; }}
    .pill {{ font: 500 10px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; text-anchor: middle; }}"""


def num(value):
    return "—" if value is None else f"{value:,}"


def dim(value):
    """Mute unknown values so a placeholder never reads as a broken render."""
    return ' opacity=".35"' if value is None else ""


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def truncate(text, limit):
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def wrap(text, limit, lines):
    """Greedy word wrap into at most `lines` lines of roughly `limit` chars."""
    words = str(text).split()
    out, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:  # a word longer than `limit` must not emit a blank line
            out.append(current)
        current = truncate(word, limit)
        if len(out) == lines:
            break
    if current and len(out) < lines:
        out.append(current)
    if len(out) == lines and (len(" ".join(words)) > sum(len(o) + 1 for o in out)):
        out[-1] = truncate(out[-1] + "…", limit)
    return out


def frame(width, height, title, subtitle="", body=""):
    """Open a card: rounded cream panel, pink border, two header dots, title."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
  <style>
{STYLE}
  </style>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="14" fill="{CREAM}" stroke="{PINK_SOFT}" stroke-width="2"/>
  <circle cx="34" cy="34" r="6" fill="{PINK}"/>
  <circle cx="50" cy="34" r="6" fill="{LAVENDER}"/>
  <text x="70" y="39" class="t">{esc(title)}</text>
  <text x="{width - 34}" y="39" class="s" text-anchor="end">{esc(subtitle)}</text>
{body}</svg>
"""


def http_json(url, data=None, headers=None, token=None, timeout=20):
    merged = {"User-Agent": UA, **(headers or {})}
    if token:
        merged["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=merged)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def graphql(query, variables, token, timeout=25):
    payload = json.dumps({"query": query, "variables": variables}).encode()
    result = http_json(
        "https://api.github.com/graphql",
        data=payload,
        headers={"Content-Type": "application/json"},
        token=token,
        timeout=timeout,
    )
    if "errors" in result:
        raise ValueError(f"GraphQL errors: {result['errors']}")
    if "data" not in result:
        raise ValueError(f"no data in response: {str(result)[:200]}")
    return result["data"]
