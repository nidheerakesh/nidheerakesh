#!/usr/bin/env python3
"""Refresh the projects showcase in README.md.

Picks the top public repos (stars first, most recently pushed to break ties),
renders a card SVG per repo into assets/projects/, and rewrites the block
between the PROJECTS markers to point at them. The cards are committed rather
than fetched from an image service, because the service this replaced was
permanently over quota.

On any fetch failure the README and the existing cards are left as they are.

Usage:
  projects.py                 # fetch from the GitHub API
  projects.py --from-file X   # read a repo-list JSON instead (offline seeding)
"""

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from card import (  # noqa: E402
    BROWN, INK, PALE, PINK, PINK_SOFT, RAMP,
    esc, frame, truncate, wrap,
)

USER = "nidheerakesh"
COUNT = 4
ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
CARDS = ROOT / "assets" / "projects"
START = "<!-- PROJECTS:START -->"
END = "<!-- PROJECTS:END -->"

CARD_WIDTH, CARD_HEIGHT = 400, 150

# Stable colour per language so a repo keeps its accent across refreshes.
LANGUAGE_COLORS = {
    "Python": PINK,
    "TypeScript": "#B8CAE8",
    "JavaScript": "#F7C9A8",
    "CSS": "#D9C2E9",
    "HTML": "#C7E3D4",
    "Java": "#E6E6FA",
    "Shell": "#C7E3D4",
    "C++": "#B8CAE8",
}


def fetch_repos():
    url = f"https://api.github.com/users/{USER}/repos?per_page=100&sort=pushed"
    headers = {"User-Agent": "profile-readme-projects", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def pick(repos):
    eligible = [
        r
        for r in repos
        if not r.get("private")
        and not r.get("fork")
        and not r.get("archived")
        and r.get("name", "").lower() != USER.lower()
    ]
    eligible.sort(
        key=lambda r: (r.get("stargazers_count", 0), r.get("pushed_at") or r.get("updated_at") or ""),
        reverse=True,
    )
    return eligible[:COUNT]


def render_card(repo):
    name = repo["name"]
    language = repo.get("language")
    accent = LANGUAGE_COLORS.get(language, RAMP[len(name) % len(RAMP)])
    description = repo.get("description") or "No description yet."

    body = ""
    y = 76
    for line in wrap(description, 44, 2):
        body += f'  <text x="34" y="{y}" class="s">{esc(line)}</text>\n'
        y += 17

    footer = CARD_HEIGHT - 26
    body += f'  <circle cx="39" cy="{footer - 4}" r="5" fill="{accent}"/>\n'
    body += (
        f'  <text x="52" y="{footer}" class="s">'
        f'{esc(language or "—")}</text>\n'
    )
    body += (
        f'  <text x="{CARD_WIDTH - 34}" y="{footer}" class="s" text-anchor="end">'
        f'{repo.get("stargazers_count", 0)} stars · {repo.get("forks_count", 0)} forks</text>\n'
    )

    return frame(CARD_WIDTH, CARD_HEIGHT, truncate(name, 24), "", body)


def write_cards(repos):
    CARDS.mkdir(parents=True, exist_ok=True)
    keep = set()
    for repo in repos:
        path = CARDS / f"{repo['name']}.svg"
        path.write_text(render_card(repo))
        keep.add(path.name)

    # Drop cards for repos that dropped out of the top four.
    for stale in CARDS.glob("*.svg"):
        if stale.name not in keep:
            stale.unlink()
            print(f"removed stale card {stale.name}")


def render_block(repos):
    if not repos:
        return (
            '<p align="center">\n'
            "  <em>No public projects to show yet — this refreshes itself.</em>\n"
            "</p>\n"
        )
    lines = ['<div align="center">\n  <table>\n    <tr>\n']
    for index, repo in enumerate(repos):
        if index and index % 2 == 0:
            lines.append("    </tr>\n    <tr>\n")
        name = repo["name"]
        lines.append(
            f"      <td>\n"
            f'        <a href="https://github.com/{USER}/{name}">\n'
            f'          <img src="./assets/projects/{name}.svg" alt="{esc(name)}" />\n'
            f"        </a>\n"
            f"      </td>\n"
        )
    lines.append("    </tr>\n  </table>\n</div>\n")
    return "".join(lines)


def main():
    if "--from-file" in sys.argv:
        path = sys.argv[sys.argv.index("--from-file") + 1]
        repos = json.loads(pathlib.Path(path).read_text())
        print(f"loaded {len(repos)} repos from {path}")
    else:
        try:
            repos = fetch_repos()
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            print(f"repo fetch failed ({type(exc).__name__}: {exc}); leaving README untouched")
            return 0
        if not isinstance(repos, list):
            print(f"unexpected API response: {str(repos)[:200]}; leaving README untouched")
            return 0

    picked = pick(repos)
    print("featuring: " + (", ".join(r["name"] for r in picked) or "(none)"))
    write_cards(picked)

    text = README.read_text()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        print(f"markers {START} / {END} not found in README; nothing to do")
        return 0

    README.write_text(pattern.sub(f"{START}\n{render_block(picked)}{END}", text))
    print("README projects block updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
