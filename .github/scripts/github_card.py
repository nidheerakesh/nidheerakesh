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
    BROWN, CREAM, INK, PALE, PINK, PINK_SOFT, RAMP,
    dim, esc, frame, graphql, num, truncate,
)

USER = "nidheerakesh"
ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / ".github" / "data" / "github.json"
STATS_OUT = ROOT / "assets" / "github-card.svg"
LANGS_OUT = ROOT / "assets" / "langs-card.svg"

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
      contributionCalendar { totalContributions }
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


def fetch(token):
    data = graphql(QUERY, {"login": USER}, token)
    user = data.get("user")
    if not user:
        raise ValueError(f"no such GitHub user '{USER}'")

    contributions = user["contributionsCollection"]
    repos = user["repositories"]["nodes"] or []

    languages = {}
    for repo in repos:
        for edge in (repo.get("languages") or {}).get("edges") or []:
            name = edge["node"]["name"]
            languages[name] = languages.get(name, 0) + edge["size"]

    return {
        "contributions": contributions["contributionCalendar"]["totalContributions"],
        "commits": contributions["totalCommitContributions"],
        "prs": contributions["totalPullRequestContributions"],
        "issues": contributions["totalIssueContributions"],
        "reviews": contributions["totalPullRequestReviewContributions"],
        "stars": sum(r.get("stargazerCount", 0) for r in repos),
        "repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "languages": dict(
            sorted(languages.items(), key=lambda kv: kv[1], reverse=True)[:TOP_LANGS]
        ),
    }


# ----------------------------------------------------------------------- render


def render_stats(stats):
    """Hero contribution count, then two rows of three supporting numbers."""
    cells = [
        ("commits", "COMMITS"),
        ("prs", "PULL REQUESTS"),
        ("issues", "ISSUES"),
        ("stars", "STARS EARNED"),
        ("repos", "REPOSITORIES"),
        ("followers", "FOLLOWERS"),
    ]

    body = (
        f'  <text x="34" y="96" class="big"{dim(stats.get("contributions"))}>'
        f'{num(stats.get("contributions"))}</text>\n'
        f'  <text x="34" y="112" class="cap">CONTRIBUTIONS THIS YEAR</text>\n'
        f'  <line x1="34" y1="130" x2="426" y2="130" stroke="{PINK_SOFT}" stroke-width="1"/>\n'
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

    return frame(460, 262, "github", f"@{USER}", body)


def render_langs(languages):
    """One stacked proportional bar, then a two-column legend."""
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
            f'fill="none" stroke="{CREAM}" stroke-width="2"/>\n'
        )
    else:
        body += (
            f'  <rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="16" rx="8" '
            f'fill="{PALE}"/>\n'
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

    return frame(460, max(y + 30, 180), "languages", f"@{USER}", body)


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
    STATS_OUT.write_text(render_stats(stats))
    LANGS_OUT.write_text(render_langs(stats.get("languages") or {}))
    print(f"wrote {STATS_OUT.name} and {LANGS_OUT.name} (live={live})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
