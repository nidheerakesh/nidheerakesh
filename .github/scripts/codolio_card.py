#!/usr/bin/env python3
"""Render assets/codolio-card.svg from Codolio profile stats.

Codolio has no official README widget, so this probes their public profile
endpoints and draws the card itself. Any failure falls back to the values in
.github/data/codolio.json and still writes a valid card -- the README must
never show a broken image, and this script must never fail the workflow.
"""

import json
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import date

HANDLE = "nidhirakesh05"
ROOT = pathlib.Path(__file__).resolve().parents[2]
FALLBACK = ROOT / ".github" / "data" / "codolio.json"
OUT = ROOT / "assets" / "codolio-card.svg"

# Tried in order; the first one that yields usable numbers wins.
ENDPOINTS = [
    f"https://codolio.com/api/profile/{HANDLE}",
    f"https://codolio.com/api/v1/public/profile/{HANDLE}",
    f"https://codolio.com/api/public/profile/{HANDLE}",
    f"https://codolio.com/api/user/{HANDLE}",
    f"https://api.codolio.com/profile/{HANDLE}",
]

CREAM = "#FDF6EC"
PINK = "#FFB6C1"
PINK_SOFT = "#FFD9E0"
LAVENDER = "#E6E6FA"
INK = "#5F78A7"
PALE = "#E7EEF8"
BROWN = "#8B5E4B"

PLATFORMS = ("LeetCode", "Codeforces", "CodeChef")
PLATFORM_COLORS = {"LeetCode": PINK, "Codeforces": "#B8CAE8", "CodeChef": LAVENDER}

# Key spellings seen across coding-profile aggregators, lowercased.
TOTAL_KEYS = {
    "totalquestions", "totalsolved", "totalquestionssolved", "questionssolved",
    "totalproblemssolved", "problemssolved", "solvedcount",
}
ACTIVE_KEYS = {"totaldays", "activedays", "totalactivedays"}
CONTEST_KEYS = {"totalcontests", "contestsattended", "contestcount", "contests"}


def walk(node):
    """Yield every (lowercased key, value) pair anywhere in the JSON."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key).lower(), value
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def find_int(data, keys):
    for key, value in walk(data):
        if key in keys and isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return None


def find_platform(data, name):
    """Find a per-platform solved count, e.g. {"leetcode": {"solved": 250}}."""
    target = name.lower()
    for key, value in walk(data):
        if key != target:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        if isinstance(value, dict):
            count = find_int(value, TOTAL_KEYS | {"count", "solved", "total"})
            if count is not None:
                return count
    return None


def fetch():
    for url in ENDPOINTS:
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "profile-readme-card", "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status != 200:
                    print(f"  {url} -> HTTP {response.status}")
                    continue
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            print(f"  {url} -> {type(exc).__name__}: {exc}")
            continue

        stats = {
            "totalSolved": find_int(payload, TOTAL_KEYS),
            "platforms": {name: find_platform(payload, name) for name in PLATFORMS},
            "activeDays": find_int(payload, ACTIVE_KEYS),
            "contests": find_int(payload, CONTEST_KEYS),
        }
        if stats["totalSolved"] is not None or any(stats["platforms"].values()):
            print(f"  {url} -> OK")
            return stats, url
        print(f"  {url} -> 200 but no recognisable stats in payload")
    return None, None


def load_fallback():
    try:
        data = json.loads(FALLBACK.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"fallback unreadable ({exc}); rendering an empty card")
        return {"totalSolved": None, "platforms": {}, "activeDays": None, "contests": None}
    return {
        "totalSolved": data.get("totalSolved"),
        "platforms": data.get("platforms", {}),
        "activeDays": data.get("activeDays"),
        "contests": data.get("contests"),
    }


def save_fallback(stats):
    """Keep the checked-in numbers fresh so an outage degrades to recent data."""
    try:
        data = json.loads(FALLBACK.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    data.update(
        {
            "handle": HANDLE,
            "totalSolved": stats["totalSolved"],
            "platforms": stats["platforms"],
            "activeDays": stats["activeDays"],
            "contests": stats["contests"],
        }
    )
    FALLBACK.write_text(json.dumps(data, indent=2) + "\n")


def num(value):
    return "—" if value is None else f"{value:,}"


def dim(value):
    """Mute unknown values so a placeholder never reads as a broken render."""
    return ' opacity=".35"' if value is None else ""


def render(stats, live):
    values = [v for v in stats.get("platforms", {}).values() if isinstance(v, int)]
    scale = max(values) if values else 0

    rows = []
    y = 132
    for name in PLATFORMS:
        count = stats.get("platforms", {}).get(name)
        width = round(150 * count / scale) if (scale and isinstance(count, int)) else 0
        rows.append(
            f'  <text x="34" y="{y + 11}" class="lbl">{name}</text>\n'
            f'  <rect x="150" y="{y}" width="150" height="14" rx="7" fill="{PALE}"/>\n'
            + (
                f'  <rect x="150" y="{y}" width="{width}" height="14" rx="7" '
                f'fill="{PLATFORM_COLORS[name]}"/>\n'
                if width
                else ""
            )
            + f'  <text x="386" y="{y + 11}" class="val"{dim(count)}>{num(count)}</text>\n'
        )
        y += 30

    note = (
        f"synced {date.today().isoformat()}"
        if live
        else "syncing — showing last known values"
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="250" viewBox="0 0 420 250" role="img" aria-label="Codolio coding stats for {HANDLE}">
  <style>
    .t {{ font: 600 17px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; }}
    .s {{ font: 400 11px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .75; }}
    .big {{ font: 700 38px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; }}
    .mid {{ font: 700 20px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; text-anchor: middle; }}
    .cap {{ font: 400 9px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .7; letter-spacing: .8px; }}
    .capm {{ font: 400 9px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .7; letter-spacing: .8px; text-anchor: middle; }}
    .lbl {{ font: 500 12px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; }}
    .val {{ font: 600 12px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; text-anchor: end; }}
  </style>
  <rect x="1" y="1" width="418" height="248" rx="14" fill="{CREAM}" stroke="{PINK_SOFT}" stroke-width="2"/>
  <circle cx="34" cy="34" r="6" fill="{PINK}"/>
  <circle cx="50" cy="34" r="6" fill="{LAVENDER}"/>
  <text x="70" y="39" class="t">codolio</text>
  <text x="145" y="39" class="s">@{HANDLE}</text>
  <text x="34" y="90" class="big"{dim(stats.get('totalSolved'))}>{num(stats.get('totalSolved'))}</text>
  <text x="34" y="105" class="cap">TOTAL SOLVED</text>
  <text x="280" y="86" class="mid"{dim(stats.get('activeDays'))}>{num(stats.get('activeDays'))}</text>
  <text x="280" y="102" class="capm">ACTIVE DAYS</text>
  <text x="370" y="86" class="mid"{dim(stats.get('contests'))}>{num(stats.get('contests'))}</text>
  <text x="370" y="102" class="capm">CONTESTS</text>
  <line x1="34" y1="118" x2="386" y2="118" stroke="{PINK_SOFT}" stroke-width="1"/>
{''.join(rows)}  <text x="34" y="232" class="s">{note}</text>
  <text x="386" y="232" class="s" text-anchor="end">✿</text>
</svg>
"""


def main():
    print("probing Codolio endpoints:")
    stats, source = fetch()
    live = stats is not None
    if live:
        print(f"live data from {source}")
        save_fallback(stats)
    else:
        print("all endpoints failed — using .github/data/codolio.json")
        stats = load_fallback()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(stats, live))
    print(f"wrote {OUT.relative_to(ROOT)} (live={live})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
