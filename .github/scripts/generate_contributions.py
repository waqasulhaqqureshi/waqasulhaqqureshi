import html
import json
import os
from datetime import date, datetime, timezone
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
            contributionLevel
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

LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

PALETTES = {
    "light": {
        "background": "#ffffff",
        "text": "#57606a",
        "colors": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    },
    "dark": {
        "background": "#0d1117",
        "text": "#c9d1d9",
        "colors": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    },
}

CELL = 11
GAP = 3
STEP = CELL + GAP
LEFT = 34
GRID_TOP = 51


def get_calendar(username: str, token: str) -> dict:
    body = json.dumps(
        {"query": QUERY, "variables": {"login": username}}
    ).encode("utf-8")
    request = Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-contribution-calendar",
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


def svg_for(calendar: dict, palette_name: str, updated: str) -> str:
    palette = PALETTES[palette_name]
    colors = palette["colors"]
    weeks = calendar["weeks"]
    months = calendar["months"]
    width = LEFT + len(weeks) * STEP + 8
    height = GRID_TOP + 7 * STEP + 28
    total = f"{calendar['totalContributions']:,}"
    title = f"{total} contributions in the last year, updated {updated} UTC"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"  <title id=\"title\">{html.escape(title)}</title>",
        f'  <desc id="desc">A dated calendar of daily GitHub contributions over the past year. Hover a square to see its date and count.</desc>',
        f'  <rect class="background" width="100%" height="100%" rx="6" fill="{palette["background"]}"/>',
        f'  <g fill="{palette["text"]}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">',
        f'    <text x="0" y="17" font-size="13" font-weight="600">{total} contributions in the last year</text>',
        f'    <text x="{width}" y="17" text-anchor="end" font-size="10">Updated {updated} UTC</text>',
    ]

    start = date.fromisoformat(weeks[0]["firstDay"])
    for month in months:
        month_day = date.fromisoformat(month["firstDay"])
        column = max(0, min(len(weeks) - 1, (month_day - start).days // 7))
        label = html.escape(month["name"][:3])
        parts.append(
            f'    <text x="{LEFT + column * STEP}" y="39" font-size="10">{label}</text>'
        )

    for weekday, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = GRID_TOP + weekday * STEP + CELL - 1
        parts.append(f'    <text x="0" y="{y}" font-size="9">{label}</text>')
    parts.append("  </g>")

    for column, week in enumerate(weeks):
        x = LEFT + column * STEP
        for day in week["contributionDays"]:
            row = int(day["weekday"])
            level = LEVELS.get(day["contributionLevel"], 0)
            fill = colors[level]
            count = int(day["contributionCount"])
            noun = "contribution" if count == 1 else "contributions"
            tooltip = html.escape(f"{day['date']}: {count} {noun}")
            y = GRID_TOP + row * STEP
            parts.append(
                f'  <g><title>{tooltip}</title><rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"/></g>'
            )

    legend_y = GRID_TOP + 7 * STEP + 14
    legend_x = width - 108
    parts.append(
        f'  <g fill="{palette["text"]}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="9">'
    )
    parts.append(f'    <text x="{legend_x - 23}" y="{legend_y + 9}">Less</text>')
    for index, fill in enumerate(colors):
        x = legend_x + index * 13
        parts.append(
            f'    <rect x="{x}" y="{legend_y}" width="10" height="10" rx="2" fill="{fill}"/>'
        )
    parts.append(
        f'    <text x="{legend_x + len(colors) * 13 + 2}" y="{legend_y + 9}">More</text>'
    )
    parts.append("  </g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    username = os.environ.get("GITHUB_USERNAME", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not username or not token:
        raise RuntimeError("GITHUB_USERNAME and GITHUB_TOKEN are required")

    calendar = get_calendar(username, token)
    updated = datetime.now(timezone.utc).date().isoformat()
    output = Path("dist")
    output.mkdir(parents=True, exist_ok=True)

    for palette_name in PALETTES:
        filename = f"github-contributions{'-dark' if palette_name == 'dark' else ''}.svg"
        (output / filename).write_text(
            svg_for(calendar, palette_name, updated), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
