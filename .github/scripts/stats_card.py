#!/usr/bin/env python3
"""Render assets/dsa-card.svg from the LeetCode, Codeforces and CodeChef APIs.

Each platform is fetched independently: one being down or changing shape mutes
that row instead of blanking the card. Every successful lookup is cached to
.github/data/stats.json, so a later outage falls back to the last known numbers
rather than dashes. This script never fails the workflow.
"""

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
from datetime import date

LEETCODE = "nidhirakesh05"
CODEFORCES = "nidhirakesh05"
CODECHEF = "nidhirakesh05"

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / ".github" / "data" / "stats.json"
OUT = ROOT / "assets" / "dsa-card.svg"

UA = "Mozilla/5.0 (compatible; profile-readme-card/1.0; +https://github.com/nidheerakesh)"

CREAM = "#FDF6EC"
PINK = "#FFB6C1"
PINK_SOFT = "#FFD9E0"
LAVENDER = "#E6E6FA"
INK = "#5F78A7"
PALE = "#E7EEF8"
BROWN = "#8B5E4B"

ROW_COLORS = {"LeetCode": PINK, "Codeforces": "#B8CAE8", "CodeChef": LAVENDER}


def get(url, data=None, headers=None, timeout=20):
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": UA, **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


# --------------------------------------------------------------------- LeetCode

LEETCODE_QUERY = """
query userStats($username: String!) {
  matchedUser(username: $username) {
    profile { ranking }
    submitStatsGlobal { acSubmissionNum { difficulty count } }
  }
  userContestRanking(username: $username) { rating attendedContestsCount }
}
"""


def fetch_leetcode():
    payload = json.dumps(
        {"query": LEETCODE_QUERY, "variables": {"username": LEETCODE}}
    ).encode()
    body = get(
        "https://leetcode.com/graphql",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Referer": f"https://leetcode.com/{LEETCODE}/",
        },
    )
    data = json.loads(body)["data"]
    user = data.get("matchedUser")
    if not user:
        raise ValueError(f"no LeetCode user '{LEETCODE}'")

    counts = {
        entry["difficulty"]: entry["count"]
        for entry in user["submitStatsGlobal"]["acSubmissionNum"]
    }
    contest = data.get("userContestRanking") or {}
    return {
        "solved": counts.get("All"),
        "easy": counts.get("Easy"),
        "medium": counts.get("Medium"),
        "hard": counts.get("Hard"),
        "rating": round(contest["rating"]) if contest.get("rating") else None,
        "contests": contest.get("attendedContestsCount"),
        "note": None,
    }


# ------------------------------------------------------------------ Codeforces


def fetch_codeforces():
    info = json.loads(get(f"https://codeforces.com/api/user.info?handles={CODEFORCES}"))
    if info.get("status") != "OK" or not info.get("result"):
        raise ValueError(f"user.info: {info.get('comment', 'unexpected response')}")
    user = info["result"][0]

    solved = None
    try:
        status = json.loads(
            get(f"https://codeforces.com/api/user.status?handle={CODEFORCES}&from=1&count=10000")
        )
        if status.get("status") == "OK":
            solved = len(
                {
                    (s["problem"].get("contestId"), s["problem"].get("index"))
                    for s in status["result"]
                    if s.get("verdict") == "OK"
                }
            )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, OSError) as exc:
        print(f"  codeforces user.status failed ({type(exc).__name__}); rating only")

    return {
        "solved": solved,
        "rating": user.get("rating"),
        "maxRating": user.get("maxRating"),
        "note": user.get("rank"),
    }


# --------------------------------------------------------------------- CodeChef

# CodeChef has no public API, so this reads the profile page. Each number is
# matched independently and may legitimately come back None after a redesign.
CODECHEF_PATTERNS = {
    "rating": [r'class="rating-number"[^>]*>\s*(\d{3,4})'],
    "stars": [r'class="rating"[^>]*>\s*(\d)\s*&#9733;', r'class="rating"[^>]*>\s*(\d)\s*★'],
    "solved": [
        r"Total Problems Solved:\s*(?:<[^>]*>\s*)*(\d+)",
        r"Problems Solved\s*(?:<[^>]*>\s*)*(\d+)",
        r'"problemsSolved"\s*:\s*(\d+)',
    ],
}


def fetch_codechef():
    html = get(f"https://www.codechef.com/users/{CODECHEF}", timeout=25)
    if "Page not found" in html or len(html) < 500:
        raise ValueError(f"no CodeChef user '{CODECHEF}'")

    found = {}
    for field, patterns in CODECHEF_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                found[field] = int(match.group(1))
                break
        else:
            print(f"  codechef: could not find {field} on the profile page")

    if not found:
        raise ValueError("profile page matched none of the known layouts")

    stars = found.get("stars")
    return {
        "solved": found.get("solved"),
        "rating": found.get("rating"),
        "note": f"{stars}★" if stars else None,
    }


PLATFORMS = [
    ("LeetCode", fetch_leetcode),
    ("Codeforces", fetch_codeforces),
    ("CodeChef", fetch_codechef),
]


# ----------------------------------------------------------------------- render


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


def pill_text(stats):
    rating = stats.get("rating")
    note = stats.get("note")
    if rating and note:
        return f"{rating} · {note}"
    if rating:
        return str(rating)
    if note:
        return str(note)
    return "unrated"


def render(all_stats, stale):
    solved = {name: all_stats.get(name, {}).get("solved") for name, _ in PLATFORMS}
    known = [v for v in solved.values() if isinstance(v, int)]
    total = sum(known) if known else None
    scale = max(known) if known else 0

    leet = all_stats.get("LeetCode", {})
    contests = leet.get("contests")
    best = max(
        (
            s.get("rating") or 0
            for s in all_stats.values()
            if isinstance(s.get("rating"), int)
        ),
        default=None,
    ) or None

    rows = []
    y = 140
    for name, _ in PLATFORMS:
        stats = all_stats.get(name, {})
        count = solved[name]
        width = round(140 * count / scale) if (scale and isinstance(count, int)) else 0
        muted = ' opacity=".45"' if not stats else ""
        rows.append(
            f'  <g{muted}>\n'
            f'    <circle cx="40" cy="{y + 7}" r="4" fill="{ROW_COLORS[name]}"/>\n'
            f'    <text x="52" y="{y + 11}" class="lbl">{name}</text>\n'
            f'    <rect x="130" y="{y}" width="140" height="14" rx="7" fill="{PALE}"/>\n'
            + (
                f'    <rect x="130" y="{y}" width="{width}" height="14" rx="7" '
                f'fill="{ROW_COLORS[name]}"/>\n'
                if width
                else ""
            )
            + f'    <text x="306" y="{y + 11}" class="val"{dim(count)}>{num(count)}</text>\n'
            f'    <rect x="320" y="{y - 1}" width="106" height="16" rx="8" fill="{PALE}"/>\n'
            f'    <text x="373" y="{y + 11}" class="pill">{esc(pill_text(stats))}</text>\n'
            f'  </g>\n'
        )
        y += 36

    note = (
        "showing last known values — a platform lookup failed"
        if stale
        else f"synced {date.today().isoformat()}"
    )
    breakdown = ""
    if leet.get("easy") is not None:
        breakdown = (
            f"leetcode · {leet.get('easy')} easy · "
            f"{leet.get('medium')} medium · {leet.get('hard')} hard"
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="460" height="272" viewBox="0 0 460 272" role="img" aria-label="DSA and competitive programming stats">
  <style>
    .t {{ font: 600 17px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; }}
    .s {{ font: 400 11px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .75; }}
    .big {{ font: 700 38px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; }}
    .mid {{ font: 700 20px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; text-anchor: middle; }}
    .cap {{ font: 400 9px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .7; letter-spacing: .8px; }}
    .capm {{ font: 400 9px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; opacity: .7; letter-spacing: .8px; text-anchor: middle; }}
    .lbl {{ font: 500 12px 'Segoe UI', Ubuntu, sans-serif; fill: {BROWN}; }}
    .val {{ font: 600 12px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; text-anchor: end; }}
    .pill {{ font: 500 10px 'Segoe UI', Ubuntu, sans-serif; fill: {INK}; text-anchor: middle; }}
  </style>
  <rect x="1" y="1" width="458" height="270" rx="14" fill="{CREAM}" stroke="{PINK_SOFT}" stroke-width="2"/>
  <circle cx="34" cy="34" r="6" fill="{PINK}"/>
  <circle cx="50" cy="34" r="6" fill="{LAVENDER}"/>
  <text x="70" y="39" class="t">dsa &amp; cp</text>
  <text x="426" y="39" class="s" text-anchor="end">@{esc(LEETCODE)}</text>
  <text x="34" y="92" class="big"{dim(total)}>{num(total)}</text>
  <text x="34" y="107" class="cap">TOTAL SOLVED</text>
  <text x="300" y="88" class="mid"{dim(contests)}>{num(contests)}</text>
  <text x="300" y="104" class="capm">CONTESTS</text>
  <text x="392" y="88" class="mid"{dim(best)}>{num(best)}</text>
  <text x="392" y="104" class="capm">BEST RATING</text>
  <line x1="34" y1="124" x2="426" y2="124" stroke="{PINK_SOFT}" stroke-width="1"/>
{''.join(rows)}  <text x="34" y="254" class="s">{esc(breakdown)}</text>
  <text x="426" y="254" class="s" text-anchor="end">{esc(note)}</text>
</svg>
"""


# ------------------------------------------------------------------------- main


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def main():
    cached = load_cache()
    fresh = {}
    stale = False

    for name, fetch in PLATFORMS:
        try:
            fresh[name] = fetch()
            print(f"{name}: ok — {fresh[name]}")
        except Exception as exc:  # any platform failure is survivable
            print(f"{name}: failed ({type(exc).__name__}: {exc})")
            if isinstance(cached.get(name), dict):
                fresh[name] = cached[name]
                print(f"{name}: using cached values")
            stale = True

    if fresh:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(fresh, stale))
    print(f"wrote {OUT.relative_to(ROOT)} ({len(fresh)}/{len(PLATFORMS)} platforms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
