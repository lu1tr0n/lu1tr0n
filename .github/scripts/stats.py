"""Render the profile stats cards as static SVGs from the GitHub GraphQL API."""

import json
import os
import urllib.request
from html import escape
from pathlib import Path

USER = os.environ.get("GITHUB_USER", "lu1tr0n")
OUT = Path(__file__).resolve().parents[2] / "assets" / "stats"
TOP_LANGS = 8
IGNORED_LANGS = {"Roff", "Batchfile", "Makefile", "Dockerfile", "Procfile"}

BG, TITLE, TEXT, ICON = "#1a1b27", "#70a5fd", "#38bdae", "#bf91f3"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    name
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
    contributionsCollection { totalCommitContributions }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(variables):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def fetch():
    user, repos, cursor = None, [], None
    while True:
        page = graphql({"login": USER, "cursor": cursor})
        user = user or page
        repos += page["repositories"]["nodes"]
        info = page["repositories"]["pageInfo"]
        if not info["hasNextPage"]:
            return user, repos
        cursor = info["endCursor"]


def card(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
  <title>{escape(title)}</title>
  <rect width="{width}" height="{height}" rx="4.5" fill="{BG}"/>
  <text x="25" y="35" fill="{TITLE}" font-family="{FONT}" font-size="18" font-weight="600">{escape(title)}</text>
{body}</svg>
"""


def overview(user, repos):
    rows = [
        ("Total stars", sum(r["stargazerCount"] for r in repos)),
        ("Commits (last year)", user["contributionsCollection"]["totalCommitContributions"]),
        ("Pull requests", user["pullRequests"]["totalCount"]),
        ("Issues", user["issues"]["totalCount"]),
        ("Contributed to", user["repositoriesContributedTo"]["totalCount"]),
    ]
    body = ""
    for i, (label, value) in enumerate(rows):
        y = 70 + i * 25
        body += (
            f'  <circle cx="31" cy="{y - 5}" r="4" fill="{ICON}"/>\n'
            f'  <text x="45" y="{y}" fill="{TEXT}" font-family="{FONT}" font-size="14" font-weight="600">{label}:</text>\n'
            f'  <text x="300" y="{y}" fill="{TEXT}" font-family="{FONT}" font-size="14" font-weight="700" text-anchor="end">{value:,}</text>\n'
        )
    name = user["name"] or USER
    return card(330, 195, f"{name}'s GitHub stats", body)


def languages(repos):
    sizes, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            lang = edge["node"]["name"]
            if lang in IGNORED_LANGS:
                continue
            sizes[lang] = sizes.get(lang, 0) + edge["size"]
            colors[lang] = edge["node"]["color"] or "#858585"
    top = sorted(sizes.items(), key=lambda item: item[1], reverse=True)[:TOP_LANGS]
    total = sum(size for _, size in top) or 1

    body, x = '  <clipPath id="bar"><rect x="25" y="52" width="250" height="8" rx="4"/></clipPath>\n  <g clip-path="url(#bar)">\n', 25.0
    for lang, size in top:
        width = 250 * size / total
        body += f'    <rect x="{x:.2f}" y="52" width="{width:.2f}" height="8" fill="{colors[lang]}"/>\n'
        x += width
    body += "  </g>\n"
    for i, (lang, size) in enumerate(top):
        cx, cy = 30 + (i % 2) * 135, 85 + (i // 2) * 25
        body += (
            f'  <circle cx="{cx}" cy="{cy - 4}" r="5" fill="{colors[lang]}"/>\n'
            f'  <text x="{cx + 12}" y="{cy}" fill="{TEXT}" font-family="{FONT}" font-size="11">{escape(lang)} {100 * size / total:.1f}%</text>\n'
        )
    return card(300, 195, "Most used languages", body)


def main():
    user, repos = fetch()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "overview.svg").write_text(overview(user, repos), encoding="utf-8")
    (OUT / "languages.svg").write_text(languages(repos), encoding="utf-8")


if __name__ == "__main__":
    main()
