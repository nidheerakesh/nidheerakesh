#!/usr/bin/env python3
"""Fixture tests for the card generators.

The upstream APIs are unreachable from most build environments, so correctness
rests on these rather than on live calls. Run with: python3 .github/scripts/test_cards.py

Each case below exists because it caught a real bug:
  - CodeChef's labelled total vs. a stray number near a similar heading
  - language weighting dominated by one repo's committed dataset
  - a streak reset by today not being over yet
  - dark variants leaking the light background
"""

import importlib.util
import json
import pathlib
import sys
import xml.dom.minidom

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import card  # noqa: E402

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  pass  {label}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"  FAIL  {label}  {detail}")


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def calendar(counts):
    return {
        "weeks": [
            {
                "contributionDays": [
                    {"date": f"2026-01-{i + 1:02d}", "contributionCount": c}
                    for i, c in enumerate(counts)
                ]
            }
        ]
    }


def test_dsa():
    print("\nDSA card (stats_card.py)")
    m = load("stats_card")

    leetcode = json.dumps({"data": {"matchedUser": {
        "profile": {"ranking": 412233},
        "submitStatsGlobal": {"acSubmissionNum": [
            {"difficulty": "All", "count": 43}, {"difficulty": "Easy", "count": 23},
            {"difficulty": "Medium", "count": 18}, {"difficulty": "Hard", "count": 2}]}},
        "userContestRanking": {"rating": 1673.48, "attendedContestsCount": 14}}})
    cf_info = json.dumps({"status": "OK", "result": [
        {"handle": "x", "rating": 632, "maxRating": 632, "rank": "newbie"}]})
    cf_status = json.dumps({"status": "OK", "result": [
        {"verdict": "OK", "problem": {"contestId": 1, "index": "A"}},
        {"verdict": "OK", "problem": {"contestId": 1, "index": "A"}},
        {"verdict": "WRONG_ANSWER", "problem": {"contestId": 1, "index": "B"}}]})
    codechef = "<html>" + "x" * 600 + '<div class="rating-number">1096</div>' \
        '<span class="rating">3&#9733;</span><h3>Total Problems Solved: 779</h3></html>'
    # A "Problems Solved" heading followed by an unrelated number must not be
    # mistaken for the total.
    decoy = "<html>" + "x" * 600 + '<div class="rating-number">1096</div>' \
        '<h3>Problems Solved</h3><div class="rank">4821</div></html>'

    def router(url, data=None, headers=None, timeout=20):
        if "leetcode.com/graphql" in url:
            return leetcode
        if "user.info" in url:
            return cf_info
        if "user.status" in url:
            return cf_status
        return codechef

    m.get = router
    lc = m.fetch_leetcode()
    check("leetcode totals", (lc["solved"], lc["hard"], lc["contests"]) == (43, 2, 14), str(lc))
    cf = m.fetch_codeforces()
    check("codeforces dedupes solved", cf["solved"] == 1, str(cf))
    check("codeforces rank", cf["note"] == "newbie", str(cf))
    cc = m.fetch_codechef()
    check("codechef labelled total", cc["solved"] == 779, str(cc))

    m.get = lambda *a, **k: decoy
    cc = m.fetch_codechef()
    check("codechef ignores a decoy number", cc["solved"] is None, str(cc))

    m.get = lambda *a, **k: json.dumps({"status": "FAILED", "comment": "not found"})
    try:
        m.fetch_codeforces()
        check("codeforces failure raises", False, "no exception")
    except Exception:
        check("codeforces failure raises", True)

    svg = m.render({"LeetCode": lc}, True, "dark")
    xml.dom.minidom.parseString(svg)
    check("dsa dark has no cream", card.THEMES["light"]["bg"] not in svg)


def test_github():
    print("\nGitHub + languages + streak (github_card.py)")
    m = load("github_card")

    for counts, expected, label in [
        ([1, 1, 1, 0, 1, 1], (2, 3), "break then live run"),
        ([1, 1, 1, 0], (3, 3), "today empty keeps the streak"),
        ([1, 1, 0, 0], (0, 2), "two empty days end it"),
        ([0, 0, 0], (0, 0), "all empty"),
        ([], (0, 0), "no data"),
    ]:
        check(f"streak: {label}", m.streaks(calendar(counts)) == expected,
              f"{counts} -> {m.streaks(calendar(counts))}")

    response = {"user": {
        "followers": {"totalCount": 1},
        "contributionsCollection": {
            "totalCommitContributions": 454, "totalPullRequestContributions": 18,
            "totalIssueContributions": 0, "totalPullRequestReviewContributions": 0,
            "contributionCalendar": {"totalContributions": 494, **calendar([1, 1, 1, 0, 1, 1])}},
        "repositories": {"totalCount": 15, "nodes": [
            {"stargazerCount": 2, "languages": {"edges": [
                {"size": 14_000_000, "node": {"name": "Python"}}]}},
            {"stargazerCount": 0, "languages": {"edges": [
                {"size": 5000, "node": {"name": "TypeScript"}}]}},
            {"stargazerCount": 0, "languages": {"edges": [
                {"size": 4000, "node": {"name": "TypeScript"}}]}},
            {"stargazerCount": 0, "languages": {"edges": [
                {"size": 100, "node": {"name": "TypeScript"}},
                {"size": 90, "node": {"name": "CSS"}}]}}]}}}
    m.graphql = lambda q, v, t, timeout=25: response
    stats = m.fetch("tok")
    check("stars summed across repos", stats["stars"] == 2, str(stats["stars"]))
    check("languages weighted by repo count",
          stats["language_repos"] == {"TypeScript": 3, "Python": 1, "CSS": 1},
          str(stats["language_repos"]))
    check("one big dataset no longer dominates",
          list(stats["language_repos"])[0] == "TypeScript")

    m.graphql = lambda q, v, t, timeout=25: {"user": None}
    try:
        m.fetch("tok")
        check("unknown user raises", False, "no exception")
    except Exception:
        check("unknown user raises", True)

    bar = m.render_langs(stats["language_repos"], "light")
    import re
    widths = [int(w) for w in re.findall(r'y="78" width="(\d+)" height="16" fill=', bar)]
    check("language bar sums to its width", sum(widths) == 392, f"{widths} -> {sum(widths)}")

    for name, svg in [("stats", m.render_stats(stats, "dark")),
                      ("langs", m.render_langs(stats["language_repos"], "dark")),
                      ("streak", m.render_streak(stats, "dark"))]:
        xml.dom.minidom.parseString(svg)
        check(f"{name} dark has no cream", card.THEMES["light"]["bg"] not in svg)


def test_oss():
    print("\nOpen source card (oss_card.py)")
    m = load("oss_card")
    search = {"items": [
        {"repository_url": "https://api.github.com/repos/tqec/tqec",
         "pull_request": {"merged_at": "2026-10-08T14:39:43Z"}},
        {"repository_url": "https://api.github.com/repos/tqec/tqec",
         "pull_request": {"merged_at": "2026-10-08T15:21:18Z"}},
        {"repository_url": "https://api.github.com/repos/qutip/qutip",
         "pull_request": {"merged_at": "2026-10-08T14:30:11Z"}},
        {"repository_url": "https://api.github.com/repos/quantumlib/Cirq",
         "pull_request": {"merged_at": None}}]}
    m.http_json = lambda *a, **k: search
    stats = m.fetch("tok")
    check("counts prs, merges and repos",
          (stats["prs"], stats["merged"], stats["repos"]) == (4, 3, 3), str(stats))
    check("busiest repo ranks first",
          stats["top"][0] == {"repo": "tqec/tqec", "prs": 2, "merged": 2}, str(stats["top"][0]))
    check("unmerged repo still listed",
          any(e["repo"] == "quantumlib/Cirq" for e in stats["top"]))

    m.http_json = lambda *a, **k: {"message": "API rate limit exceeded"}
    try:
        m.fetch("tok")
        check("missing items raises", False, "no exception")
    except Exception:
        check("missing items raises", True)

    svg = m.render(stats, "dark")
    xml.dom.minidom.parseString(svg)
    check("oss dark has no cream", card.THEMES["light"]["bg"] not in svg)


def test_helpers():
    print("\nShared helpers (card.py)")
    check("wrap never emits a blank line",
          all(line for line in card.wrap("Supercalifragilistic extra words", 20, 2)))
    check("wrap respects the line budget",
          len(card.wrap("one two three four five six seven eight", 12, 2)) == 2)
    check("wrap handles empty text", card.wrap("", 20, 2) == [])
    check("esc escapes markup", card.esc('<a href="x">&') == "&lt;a href=&quot;x&quot;&gt;&amp;")
    check("num formats thousands", card.num(1234) == "1,234")
    check("num shows a dash for unknown", card.num(None) == "—")
    check("dim mutes only unknowns", card.dim(None) and not card.dim(0))


def main():
    test_helpers()
    test_dsa()
    test_github()
    test_oss()
    print()
    if failures:
        print(f"{len(failures)} failure(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
