#!/usr/bin/env python3
"""Generate the wiki's Zeiterfassung page from GitLab time tracking.

Pulls every individual time log (`/spend`) via the GitLab GraphQL API — the REST
`time_stats` endpoint only exposes per-issue totals without dates, so it cannot
produce a weekly breakdown. Renders four sections: total time on top, time per
ISO week, summed time per issue, and time per day (with the issue IDs touched
that day).

Usage:
    export TIMETRACKING_TOKEN=<personal access token with read_api scope>
    python scripts/wiki_timelogs.py --out ../dart-tracking.wiki/Zeiterfassung.md

Without --out the page is printed to stdout.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date

HOST = "https://gitlab.tuwien.ac.at"
PROJECT = "e12225143/dart-tracking"
GRAPHQL_URL = f"{HOST}/api/graphql"
WIKI_PAGE = f"{HOST}/{PROJECT}/-/wikis/Zeiterfassung"

# Target hour budget for the thesis; shown next to the current total.
MAX_HOURS = 250

# Paginated over all timelogs of the project; timeSpent is in seconds, spentAt is
# an ISO-8601 timestamp. issue can be null (e.g. time logged on a merge request).
QUERY = """
query($fullPath: ID!, $after: String) {
  project(fullPath: $fullPath) {
    timelogs(first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes {
        timeSpent
        spentAt
        issue { iid title webUrl state }
      }
    }
  }
}
"""


def fetch_timelogs(token: str) -> list[dict]:
    """Return every timelog node of the project, following cursor pagination."""
    logs: list[dict] = []
    after: str | None = None

    while True:
        payload = json.dumps(
            {"query": QUERY, "variables": {"fullPath": PROJECT, "after": after}}
        ).encode()
        req = urllib.request.Request(
            GRAPHQL_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as exc:
            hint = " (is the token valid and does it have read_api scope?)" if exc.code in (401, 403) else ""
            sys.exit(f"GitLab GraphQL returned HTTP {exc.code}{hint}")

        if body.get("errors"):
            sys.exit("GitLab GraphQL error: " + json.dumps(body["errors"]))

        project = body.get("data", {}).get("project")
        if project is None:
            sys.exit(f"Project '{PROJECT}' not found or not accessible with this token.")

        page = project["timelogs"]
        logs.extend(page["nodes"])

        if not page["pageInfo"]["hasNextPage"]:
            return logs
        after = page["pageInfo"]["endCursor"]


def hours(seconds: int) -> str:
    """Format seconds as German-style decimal hours, e.g. 5400 -> '1,50'."""
    return f"{seconds / 3600:.2f}".replace(".", ",")


def render(logs: list[dict]) -> str:
    total = sum(log["timeSpent"] for log in logs)

    # Aggregate per ISO week, per issue and per day.
    per_week: dict[tuple[int, int], int] = defaultdict(int)
    per_issue: dict[int, dict] = {}
    per_day: dict[date, dict] = {}
    no_issue_seconds = 0

    for log in logs:
        spent = log["timeSpent"]
        day = date.fromisoformat(log["spentAt"][:10])
        iso_year, iso_week, _ = day.isocalendar()
        per_week[(iso_year, iso_week)] += spent

        day_bucket = per_day.setdefault(day, {"seconds": 0, "iids": set()})
        day_bucket["seconds"] += spent

        issue = log["issue"]
        if issue is None:
            no_issue_seconds += spent
            continue
        iid = int(issue["iid"])
        day_bucket["iids"].add(iid)
        bucket = per_issue.setdefault(
            iid,
            {
                "title": issue["title"],
                "web_url": issue["webUrl"],
                "state": issue["state"],
                "seconds": 0,
            },
        )
        bucket["seconds"] += spent

    lines = [
        f"> Generiert am {date.today().strftime('%d.%m.%Y')} aus der GitLab-API mit",
        "> `scripts/wiki_timelogs.py`. Nicht von Hand bearbeiten — Änderungen gehen",
        "> beim nächsten Lauf verloren.",
        "",
        "## Gesamt",
        "",
        f"- **Aktuell:** {hours(total)} h",
        f"- **Maximum:** {MAX_HOURS} h",
        "",
    ]

    # Per week, chronological.
    lines += ["## Pro Woche", "", "| Woche | Zeitraum | Stunden |", "|---|---|---:|"]
    for (iso_year, iso_week) in sorted(per_week):
        monday = date.fromisocalendar(iso_year, iso_week, 1)
        sunday = date.fromisocalendar(iso_year, iso_week, 7)
        span = f"{monday.strftime('%d.%m.')}–{sunday.strftime('%d.%m.%Y')}"
        lines.append(f"| KW {iso_week:02d} | {span} | {hours(per_week[(iso_year, iso_week)])} |")
    if not per_week:
        lines.append("| | _Noch keine Zeit gebucht._ | |")

    # Per issue: closed issues first, then ascending by issue ID within each
    # group. One row per issue with its summed hours.
    lines += ["", "## Pro Issue", "", "| Issue | Titel | Status | Stunden |", "|---|---|---|---:|"]
    for iid, data in sorted(
        per_issue.items(), key=lambda item: (item[1]["state"] != "closed", item[0])
    ):
        state = "geschlossen" if data["state"] == "closed" else "offen"
        title = data["title"].replace("|", "\\|")
        lines.append(f"| [#{iid}]({data['web_url']}) | {title} | {state} | {hours(data['seconds'])} |")
    if no_issue_seconds:
        lines.append(f"| — | _ohne Issue_ | | {hours(no_issue_seconds)} |")
    if not per_issue and not no_issue_seconds:
        lines.append("| | _Noch keine Zeit gebucht._ | | |")

    # Per day, chronological: only days with logged time, their total and the
    # issue IDs touched that day.
    lines += ["", "## Pro Tag", "", "| Tag | Issues | Stunden |", "|---|---|---:|"]
    for day in sorted(per_day):
        data = per_day[day]
        iids = ", ".join(f"[#{iid}]({HOST}/{PROJECT}/-/issues/{iid})" for iid in sorted(data["iids"]))
        if not iids:
            iids = "_ohne Issue_"
        lines.append(f"| {day.strftime('%d.%m.%Y')} | {iids} | {hours(data['seconds'])} |")
    if not per_day:
        lines.append("| | _Noch keine Zeit gebucht._ | |")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="write the page here instead of stdout")
    args = parser.parse_args()

    token = os.environ.get("TIMETRACKING_TOKEN")
    if not token:
        sys.exit(
            "TIMETRACKING_TOKEN is not set. A personal access token with \n"
            "read_api scope is needed"
        )

    page = render(fetch_timelogs(token))

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(page)
        print(f"wrote {args.out}")
    else:
        print(page)


if __name__ == "__main__":
    main()
