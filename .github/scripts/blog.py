#!/usr/bin/env python3
"""Refresh the latest-posts list in README.md from an RSS or Atom feed.

The feed URL comes from the BLOG_FEED environment variable (a repo variable in
CI). If it is unset, or the fetch fails, the README is left as it is.

Usage:
  BLOG_FEED=https://example.com/feed.xml python3 .github/scripts/blog.py
"""

import datetime
import email.utils
import html
import os
import pathlib
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
START = "<!-- BLOG:START -->"
END = "<!-- BLOG:END -->"
COUNT = 5
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "profile-readme-blog"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def short_date(raw):
    if not raw:
        return ""
    try:
        return email.utils.parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        pass
    try:
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def text_of(node, tag):
    found = node.find(tag)
    return (found.text or "").strip() if found is not None else ""


def parse_rss(root):
    return [
        (text_of(item, "title"), text_of(item, "link"), short_date(text_of(item, "pubDate")))
        for item in root.iter("item")
    ]


def parse_atom(root):
    posts = []
    for entry in root.iter(f"{ATOM}entry"):
        link = entry.find(f"{ATOM}link")
        href = link.get("href", "") if link is not None else ""
        date = text_of(entry, f"{ATOM}published") or text_of(entry, f"{ATOM}updated")
        posts.append((text_of(entry, f"{ATOM}title"), href, short_date(date)))
    return posts


def parse_feed(data):
    root = ET.fromstring(data)
    if root.tag == f"{ATOM}feed":
        return parse_atom(root)
    return parse_rss(root)


def render_block(posts):
    if not posts:
        return '<p align="center">\n  <em>No posts yet. This refreshes itself.</em>\n</p>\n'
    lines = ['<div align="center">\n']
    for title, link, date in posts[:COUNT]:
        lines.append(
            f'  <a href="{html.escape(link)}"><b>{html.escape(title)}</b></a>'
            f" <sub>{html.escape(date)}</sub><br />\n"
        )
    lines.append("</div>\n")
    return "".join(lines)


def main():
    feed = os.environ.get("BLOG_FEED", "").strip()
    if not feed:
        print("BLOG_FEED not set; leaving README untouched")
        return 0
    try:
        posts = parse_feed(fetch(feed))
    except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError) as exc:
        print(f"feed fetch failed ({type(exc).__name__}: {exc}); leaving README untouched")
        return 0

    text = README.read_text()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        print(f"markers {START} / {END} not found in README; nothing to do")
        return 0

    README.write_text(pattern.sub(f"{START}\n{render_block(posts)}{END}", text))
    print(f"README blog block updated with {min(len(posts), COUNT)} post(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
