"""Generate an "Activity overview" radar card from real GitHub contribution data."""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""


def fetch(username: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": username}}).encode()
    request = Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-activity-overview",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {username}")
    return user["contributionsCollection"]


def render(data: dict) -> str:
    commits = data["totalCommitContributions"]
    prs = data["totalPullRequestContributions"]
    issues = data["totalIssueContributions"]
    reviews = data["totalPullRequestReviewContributions"]
    total = data["contributionCalendar"]["totalContributions"]
    parts = commits + prs + issues + reviews
    share = lambda n: (n / parts) if parts else 0.0
    shares = {"review": share(reviews), "issues": share(issues), "prs": share(prs), "commits": share(commits)}
    top = max(shares.values()) or 1.0

    cx, cy, radius = 400, 140, 88
    # Axes: top = code review, right = issues, bottom = pull requests, left = commits.
    point = {
        "review": (cx, cy - radius * shares["review"] / top),
        "issues": (cx + radius * shares["issues"] / top, cy),
        "prs": (cx, cy + radius * shares["prs"] / top),
        "commits": (cx - radius * shares["commits"] / top, cy),
    }
    polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point["review"], point["issues"], point["prs"], point["commits"]))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#7ee787"/>' for x, y in point.values())
    pct = lambda key: f"{round(shares[key] * 100)}%"

    font = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 300" width="800" height="300" role="img" aria-label="Activity overview: {commits} commits, {prs} pull requests, {issues} issues and {reviews} code reviews in the last year">
  <rect width="800" height="300" rx="12" fill="#0d1117" stroke="#30363d"/>
  <text x="32" y="44" font-family="{font}" font-size="18" font-weight="600" fill="#e6edf3">Activity overview</text>
  <text x="32" y="68" font-family="{font}" font-size="13" fill="#8b949e">{total} contributions in the last year</text>
  <g font-family="{font}" font-size="14" fill="#c9d1d9">
    <text x="32" y="124">Commits</text><text x="190" y="124" text-anchor="end" font-weight="600">{commits}</text>
    <text x="32" y="152">Pull requests</text><text x="190" y="152" text-anchor="end" font-weight="600">{prs}</text>
    <text x="32" y="180">Issues</text><text x="190" y="180" text-anchor="end" font-weight="600">{issues}</text>
    <text x="32" y="208">Code reviews</text><text x="190" y="208" text-anchor="end" font-weight="600">{reviews}</text>
  </g>
  <line x1="260" y1="30" x2="260" y2="270" stroke="#30363d"/>
  <g stroke="#3d444d" stroke-width="1">
    <line x1="{cx}" y1="{cy - radius}" x2="{cx}" y2="{cy + radius}"/>
    <line x1="{cx - radius}" y1="{cy}" x2="{cx + radius}" y2="{cy}"/>
  </g>
  <polygon points="{polygon}" fill="#2ea043" fill-opacity="0.75" stroke="#7ee787" stroke-width="1.5" stroke-linejoin="round"/>
  {dots}
  <g font-family="{font}" font-size="12" fill="#8b949e" text-anchor="middle">
    <text x="{cx}" y="{cy - radius - 22}">{pct('review')}</text><text x="{cx}" y="{cy - radius - 8}">Code review</text>
    <text x="{cx}" y="{cy + radius + 20}">{pct('prs')}</text><text x="{cx}" y="{cy + radius + 34}">Pull requests</text>
    <text x="{cx - radius - 14}" y="{cy - 4}" text-anchor="end">{pct('commits')}</text><text x="{cx - radius - 14}" y="{cy + 12}" text-anchor="end">Commits</text>
    <text x="{cx + radius + 14}" y="{cy - 4}" text-anchor="start">{pct('issues')}</text><text x="{cx + radius + 14}" y="{cy + 12}" text-anchor="start">Issues</text>
  </g>
</svg>
"""


def main() -> None:
    username = os.environ["GITHUB_USERNAME"]
    token = os.environ["GITHUB_TOKEN"]
    out = Path("dist")
    out.mkdir(exist_ok=True)
    (out / "activity-overview.svg").write_text(render(fetch(username, token)), encoding="utf-8")


if __name__ == "__main__":
    main()
