#!/usr/bin/env python3
"""Refresh the projects showcase in README.md.

Picks the top public repos (stars first, most recently pushed to break ties)
and rewrites the block between the PROJECTS markers with themed pin cards.
On any fetch failure the README is left exactly as it is.

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

USER = "nidheerakesh"
COUNT = 4
ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
START = "<!-- PROJECTS:START -->"
END = "<!-- PROJECTS:END -->"

CARD_PARAMS = (
    "bg_color=FDF6EC&title_color=5F78A7&text_color=8B5E4B"
    "&icon_color=FFB6C1&border_color=FFD9E0&border_radius=14"
)


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


def card(repo):
    name = repo["name"]
    src = f"https://github-readme-stats.vercel.app/api/pin/?username={USER}&repo={name}&{CARD_PARAMS}"
    return (
        f'      <a href="https://github.com/{USER}/{name}">\n'
        f'        <img src="{src}" alt="{name}" />\n'
        f"      </a>\n"
    )


def render(repos):
    if not repos:
        return (
            "<p align=\"center\">\n"
            "  <em>No public projects to show yet — this refreshes itself.</em>\n"
            "</p>\n"
        )
    lines = ['<div align="center">\n  <table>\n    <tr>\n']
    for index, repo in enumerate(repos):
        if index and index % 2 == 0:
            lines.append("    </tr>\n    <tr>\n")
        lines.append("      <td>\n")
        lines.append(card(repo))
        lines.append("      </td>\n")
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

    text = README.read_text()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        print(f"markers {START} / {END} not found in README; nothing to do")
        return 0

    README.write_text(pattern.sub(f"{START}\n{render(picked)}{END}", text))
    print("README projects block updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
