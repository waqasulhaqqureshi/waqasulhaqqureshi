import html
import json
import os
import re
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          firstDay
          contributionDays {
            date
            weekday
            contributionCount
          }
        }
        months {
          name
          firstDay
        }
      }
    }
  }
}
"""

CELL_X = 2
CELL_Y = 2
STEP = 16
WEEKDAYS = ("S", "M", "T", "W", "T", "F", "S")
CELL_PATTERN = re.compile(
    r'<rect class="(c(?: c[0-9a-f]+)?)" x="([0-9.]+)" '
    r'y="([0-9.]+)" rx="2" ry="2"/>'
)


def get_calendar(username: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": username}}).encode()
    request = Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-contribution-snake",
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
    return user["contributionsCollection"]["contributionCalendar"]


def annotate_svg(path: Path, calendar: dict) -> None:
    svg = path.read_text(encoding="utf-8")
    weeks = calendar["weeks"]
    start = date.fromisoformat(weeks[0]["firstDay"])
    by_position = {}

    for column, week in enumerate(weeks):
        for day in week["contributionDays"]:
            by_position[(column, int(day["weekday"]))] = day

    def annotate_cell(match: re.Match) -> str:
        column = round((float(match.group(2)) - CELL_X) / STEP)
        weekday = round((float(match.group(3)) - CELL_Y) / STEP)
        day = by_position.get((column, weekday))
        if day is None:
            raise RuntimeError(f"No contribution date for calendar cell {column},{weekday}")
        count = int(day["contributionCount"])
        noun = "contribution" if count == 1 else "contributions"
        title = html.escape(f"{day['date']}: {count} {noun}")
        return f"<g><title>{title}</title>{match.group(0)}</g>"

    svg, cells = CELL_PATTERN.subn(annotate_cell, svg)
    if cells < 350:
        raise RuntimeError(f"Expected a full contribution grid, found only {cells} cells in {path}")

    is_dark = "-dark" in path.name
    label_color = "#8b949e" if is_dark else "#57606a"
    labels = [
        f'<g class="date-labels" fill="{label_color}" '
        'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
        'font-size="8">'
    ]

    for month in calendar["months"]:
        month_day = date.fromisoformat(month["firstDay"])
        column = max(0, min(len(weeks) - 1, (month_day - start).days // 7))
        label = html.escape(month["name"][:3])
        labels.append(
            f'<text x="{CELL_X + column * STEP}" y="-15">{label}</text>'
        )

    for weekday, label in enumerate(WEEKDAYS):
        y = CELL_Y + weekday * STEP + 10
        labels.append(f'<text x="-34" y="{y}">{label}</text>')
    labels.append("</g>")

    svg = re.sub(
        r'viewBox="-16 -32 880 192"',
        'viewBox="-36 -32 900 192"',
        svg,
        count=1,
    )
    svg = svg.replace('width="880" height="192"', 'width="900" height="192"', 1)
    svg = svg.replace("</style>", "</style>" + "".join(labels), 1)
    svg = svg.replace(
        "Generated with https://github.com/Platane/snk",
        "Generated with https://github.com/Platane/snk. Hover a square for its date and contribution count.",
        1,
    )
    path.write_text(svg, encoding="utf-8")


def main() -> None:
    username = os.environ.get("GITHUB_USERNAME", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not username or not token:
        raise RuntimeError("GITHUB_USERNAME and GITHUB_TOKEN are required")

    calendar = get_calendar(username, token)
    for name in (
        "github-contribution-grid-snake.svg",
        "github-contribution-grid-snake-dark.svg",
    ):
        path = Path("dist") / name
        if not path.is_file():
            raise FileNotFoundError(f"Contribution snake output is missing: {path}")
        annotate_svg(path, calendar)


if __name__ == "__main__":
    main()
