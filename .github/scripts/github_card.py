#!/usr/bin/env python3
"""Render assets/github-card.svg and assets/langs-card.svg from the GitHub API.

Replaces the github-readme-stats and github-profile-trophy images, whose shared
public instances are permanently over quota. One GraphQL call feeds both cards.

Falls back to .github/data/github.json when the call fails, so a bad run shows
the last known numbers instead of a broken image. Never fails the workflow.
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from card import (  # noqa: E402
    PINK, RAMP, THEMES,
    dim, esc, frame, graphql, num, truncate, write_themed,
)

USER = "nidheerakesh"
ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / ".github" / "data" / "github.json"
STATS_OUT = ROOT / "assets" / "github-card.svg"
LANGS_OUT = ROOT / "assets" / "langs-card.svg"
STREAK_OUT = ROOT / "assets" / "streak-card.svg"

TOP_LANGS = 6

QUERY = """
query profile($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def streaks(calendar):
    """Current and longest run of consecutive days with contributions.

    Days arrive oldest first. The most recent day is skipped when it is empty,
    because the day is not over yet and counting it would reset a live streak.
    """
    days = [
        day
        for week in calendar.get("weeks", [])
        for day in week.get("contributionDays", [])
    ]
    days.sort(key=lambda d: d["date"])
    counts = [d["contributionCount"] for d in days]

    longest = run = 0
    for count in counts:
        run = run + 1 if count else 0
        longest = max(longest, run)

    tail = counts[:-1] if counts and not counts[-1] else counts
    current = 0
    for count in reversed(tail):
        if not count:
            break
        current += 1

    return current, longest


def fetch(token):
    data = graphql(QUERY, {"login": USER}, token)
    user = data.get("user")
    if not user:
        raise ValueError(f"no such GitHub user '{USER}'")

    contributions = user["contributionsCollection"]
    repos = user["repositories"]["nodes"] or []

    # Weighted by how many repositories use each language, not by bytes. Byte
    # weighting let one repo with a committed dataset read as 91.8% Python,
    # which described that repo's contents rather than how the work is spread.
    language_repos = {}
    for repo in repos:
        seen = {
            edge["node"]["name"]
            for edge in (repo.get("languages") or {}).get("edges") or []
        }
        for name in seen:
            language_repos[name] = language_repos.get(name, 0) + 1

    current, longest = streaks(contributions["contributionCalendar"])

    return {
        "contributions": contributions["contributionCalendar"]["totalContributions"],
        "commits": contributions["totalCommitContributions"],
        "prs": contributions["totalPullRequestContributions"],
        "issues": contributions["totalIssueContributions"],
        "reviews": contributions["totalPullRequestReviewContributions"],
        "stars": sum(r.get("stargazerCount", 0) for r in repos),
        "repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "streak": current,
        "longest_streak": longest,
        "language_repos": dict(
            sorted(language_repos.items(), key=lambda kv: kv[1], reverse=True)[:TOP_LANGS]
        ),
    }


# ----------------------------------------------------------------------- render


def render_stats(stats, theme="light"):
    """Hero contribution count, then two rows of three supporting numbers."""
    cells = [
        ("commits", "COMMITS"),
        ("prs", "PULL REQUESTS"),
        ("issues", "ISSUES"),
        ("stars", "STARS EARNED"),
        ("repos", "REPOSITORIES"),
        ("followers", "FOLLOWERS"),
    ]

    palette = THEMES[theme]
    body = (
        f'  <text x="34" y="96" class="big"{dim(stats.get("contributions"))}>'
        f'{num(stats.get("contributions"))}</text>\n'
        f'  <text x="34" y="112" class="cap">CONTRIBUTIONS THIS YEAR</text>\n'
        f'  <line x1="34" y1="130" x2="426" y2="130" stroke="{palette["border"]}" stroke-width="1"/>\n'
    )

    for index, (key, label) in enumerate(cells):
        column, row = index % 3, index // 3
        x = 100 + column * 130
        y = 166 + row * 56
        value = stats.get(key)
        body += (
            f'  <text x="{x}" y="{y}" class="mid"{dim(value)}>{num(value)}</text>\n'
            f'  <text x="{x}" y="{y + 16}" class="capm">{label}</text>\n'
        )

    return frame(460, 262, "github", f"@{USER}", body, theme)


def render_langs(languages, theme="light"):
    """One stacked proportional bar, then a two-column legend."""
    palette = THEMES[theme]
    total = sum(languages.values()) if languages else 0
    bar_x, bar_width, bar_y = 34, 392, 78

    body = ""
    if total:
        offset = bar_x
        # Give every visible language at least a sliver, then let the last
        # segment absorb rounding so the bar always ends flush.
        items = list(languages.items())
        for index, (name, size) in enumerate(items):
            if index == len(items) - 1:
                width = bar_x + bar_width - offset
            else:
                width = max(3, round(bar_width * size / total))
                width = min(width, bar_x + bar_width - offset)
            body += (
                f'  <rect x="{offset}" y="{bar_y}" width="{width}" height="16" '
                f'fill="{RAMP[index % len(RAMP)]}"/>\n'
            )
            offset += width
        # Rounded ends without clipping the segments.
        body += (
            f'  <rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="16" rx="8" '
            f'fill="none" stroke="{palette["bg"]}" stroke-width="2"/>\n'
        )
    else:
        body += (
            f'  <rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="16" rx="8" '
            f'fill="{palette["pale"]}"/>\n'
        )

    y = 128
    for index, (name, size) in enumerate(languages.items()):
        column = index % 2
        x = 34 + column * 200
        if index and column == 0:
            y += 26
        share = f"{100 * size / total:.1f}%" if total else "—"
        body += (
            f'  <circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{RAMP[index % len(RAMP)]}"/>\n'
            f'  <text x="{x + 18}" y="{y}" class="lbl">{esc(truncate(name, 14))}</text>\n'
            f'  <text x="{x + 170}" y="{y}" class="val">{share}</text>\n'
        )

    if not languages:
        body += f'  <text x="34" y="132" class="s">no language data yet</text>\n'
        y = 132

    return frame(460, max(y + 30, 180), "languages", f"@{USER}", body, theme)


def render_streak(stats, theme="light"):
    """Longest streak, current streak in a ring, total contributions.

    Replaces streak-stats.demolab.com. The numbers come from the contribution
    calendar already fetched for the stats card, so this costs no extra call
    and removes the last external image service from the README.
    """
    palette = THEMES[theme]
    current = stats.get("streak")
    longest = stats.get("longest_streak")

    # Ring around the middle figure, filled in proportion to the personal best.
    circumference = 2 * 3.14159 * 34
    filled = (
        round(circumference * min(1.0, current / longest), 1)
        if current and longest
        else 0
    )
    body = (
        f'  <circle cx="230" cy="100" r="34" fill="none" stroke="{palette["pale"]}" stroke-width="6"/>\n'
    )
    if filled:
        body += (
            f'  <circle cx="230" cy="100" r="34" fill="none" stroke="{PINK}" stroke-width="6"'
            f' stroke-linecap="round" stroke-dasharray="{filled} {round(circumference, 1)}"'
            f' transform="rotate(-90 230 100)"/>\n'
        )

    for x, key, label in (
        (92, "longest_streak", "LONGEST STREAK"),
        (230, "streak", "CURRENT STREAK"),
        (368, "contributions", "THIS YEAR"),
    ):
        value = stats.get(key)
        body += (
            f'  <text x="{x}" y="104" class="mid"{dim(value)}>{num(value)}</text>\n'
            f'  <text x="{x}" y="{146 if x == 230 else 120}" class="capm">{label}</text>\n'
        )

    return frame(460, 172, "streak", f"@{USER}", body, theme)


# ------------------------------------------------------------------------- main


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def main():
    token = os.environ.get("GITHUB_TOKEN")
    stats, live = None, False

    if not token:
        print("no GITHUB_TOKEN in the environment; skipping the live fetch")
    else:
        try:
            stats = fetch(token)
            live = True
            print(f"github: ok — {stats}")
        except Exception as exc:  # a failed card must not fail the workflow
            print(f"github: failed ({type(exc).__name__}: {exc})")

    if stats is None:
        stats = load_cache()
        print("using cached values" if stats else "no cache; rendering placeholders")
    else:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")

    STATS_OUT.parent.mkdir(parents=True, exist_ok=True)
    write_themed(lambda theme: render_stats(stats, theme), STATS_OUT)
    write_themed(
        lambda theme: render_langs(stats.get("language_repos") or {}, theme), LANGS_OUT
    )
    write_themed(lambda theme: render_streak(stats, theme), STREAK_OUT)
    print(
        f"wrote {STATS_OUT.name}, {LANGS_OUT.name} and {STREAK_OUT.name} "
        f"(plus dark variants, live={live})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
