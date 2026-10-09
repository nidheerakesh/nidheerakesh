#!/usr/bin/env python3
"""Render assets/oss-card.svg from pull requests opened outside this account.

Uses the GitHub search API rather than contributionsCollection, because the
search result carries each PR's merged state and repository, and is not capped
to the trailing year the contributions calendar covers.

Falls back to .github/data/oss.json when the call fails, so a bad run shows the
last known numbers instead of a broken image. Never fails the workflow.
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from card import (  # noqa: E402
    PINK, RAMP, THEMES,
    dim, esc, frame, http_json, num, truncate, write_themed,
)

USER = "nidheerakesh"
ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / ".github" / "data" / "oss.json"
OUT = ROOT / "assets" / "oss-card.svg"

TOP_REPOS = 5
SEARCH = (
    "https://api.github.com/search/issues"
    f"?q=author:{USER}+-user:{USER}+is:pr&sort=created&order=desc&per_page=100"
)


def fetch(token):
    data = http_json(
        SEARCH,
        headers={"Accept": "application/vnd.github+json"},
        token=token,
        timeout=25,
    )
    items = data.get("items")
    if items is None:
        raise ValueError(f"no items in search response: {str(data)[:200]}")

    repos = {}
    merged_total = 0
    for item in items:
        # repository_url looks like https://api.github.com/repos/<owner>/<name>
        slug = "/".join(item["repository_url"].rsplit("/", 2)[-2:])
        merged = bool((item.get("pull_request") or {}).get("merged_at"))
        merged_total += merged
        entry = repos.setdefault(slug, {"prs": 0, "merged": 0})
        entry["prs"] += 1
        entry["merged"] += merged

    ranked = sorted(
        repos.items(), key=lambda kv: (kv[1]["merged"], kv[1]["prs"]), reverse=True
    )
    return {
        "prs": len(items),
        "merged": merged_total,
        "repos": len(repos),
        "top": [{"repo": slug, **counts} for slug, counts in ranked[:TOP_REPOS]],
    }


# ----------------------------------------------------------------------- render


def render(stats, theme="light"):
    palette = THEMES[theme]
    top = stats.get("top") or []

    body = (
        f'  <text x="34" y="96" class="big"{dim(stats.get("merged"))}>'
        f'{num(stats.get("merged"))}</text>\n'
        f'  <text x="34" y="112" class="cap">PULL REQUESTS MERGED</text>\n'
        f'  <text x="300" y="88" class="mid"{dim(stats.get("prs"))}>'
        f'{num(stats.get("prs"))}</text>\n'
        f'  <text x="300" y="104" class="capm">OPENED</text>\n'
        f'  <text x="392" y="88" class="mid"{dim(stats.get("repos"))}>'
        f'{num(stats.get("repos"))}</text>\n'
        f'  <text x="392" y="104" class="capm">PROJECTS</text>\n'
        f'  <line x1="34" y1="130" x2="426" y2="130" stroke="{palette["border"]}" stroke-width="1"/>\n'
    )

    y = 158
    for index, entry in enumerate(top):
        pending = entry["prs"] - entry["merged"]
        if entry["merged"] and pending:
            note = f"{entry['merged']} merged · {pending} open"
        elif entry["merged"]:
            note = f"{entry['merged']} merged"
        else:
            note = f"{pending} open"
        body += (
            f'  <circle cx="39" cy="{y - 4}" r="5" fill="{RAMP[index % len(RAMP)]}"/>\n'
            f'  <text x="52" y="{y}" class="lbl">{esc(truncate(entry["repo"], 32))}</text>\n'
            f'  <text x="426" y="{y}" class="val">{esc(note)}</text>\n'
        )
        y += 26

    if not top:
        body += '  <text x="34" y="158" class="s">no external contributions yet</text>\n'
        y = 162

    return frame(460, max(y + 14, 190), "open source", f"@{USER}", body, theme)


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
            print(f"open source: ok — {stats}")
        except Exception as exc:  # a failed card must not fail the workflow
            print(f"open source: failed ({type(exc).__name__}: {exc})")

    if stats is None:
        stats = load_cache()
        print("using cached values" if stats else "no cache; rendering placeholders")
    else:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")

    light, dark = write_themed(lambda theme: render(stats, theme), OUT)
    print(f"wrote {light.name} and {dark.name} (live={live})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
