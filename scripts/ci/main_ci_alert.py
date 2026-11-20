"""Track failed main CI runs in a single GitHub issue."""

import json
import os
import shutil
import subprocess
from typing import Any, TypedDict

TITLE = "Main CI is failing"
LABEL = "ci-main-failure"
ISSUES = "repos/{owner}/{repo}/issues"
BOT_LOGIN = "github-actions[bot]"
STATE_PREFIX = "<!-- main-ci-state "
EVENT_NAMES = {"schedule": "Scheduled CI", "push": "Push to main"}


class Run(TypedDict):
    number: int
    attempt: int
    url: str
    conclusion: str


def _gh(*args: str, stdin: str | None = None) -> str:
    executable = shutil.which("gh")
    if executable is None:
        raise RuntimeError("The GitHub CLI is required")
    # All options are reviewed and neither the issue body nor workflow data enters the shell.
    return subprocess.run(  # noqa: S603
        [executable, *args],
        input=stdin,
        stdout=subprocess.PIPE,
        check=True,
        text=True,
    ).stdout


def _api(*args: str, payload: dict[str, Any] | None = None) -> Any:
    if payload is not None:
        return json.loads(_gh("api", *args, "--input", "-", stdin=json.dumps(payload)))
    return json.loads(_gh("api", *args))


def _tracking_issue() -> dict[str, Any] | None:
    pages = _api(
        "--paginate", "--slurp", f"{ISSUES}?state=all&labels={LABEL}&per_page=100"
    )
    matches = [
        issue
        for page in pages
        for issue in page
        if issue["title"] == TITLE
        and issue["user"]["login"] == BOT_LOGIN
        and "pull_request" not in issue
    ]
    if len(matches) > 1:
        raise ValueError("Multiple main CI tracking issues found")
    return matches[0] if matches else None


def _read_state(issue_body: str) -> dict[str, Run]:
    marker = issue_body.partition("\n")[0]
    if not marker.startswith(STATE_PREFIX) or not marker.endswith(" -->"):
        raise ValueError("Main CI tracking issue is missing its automation state")
    return json.loads(marker.removeprefix(STATE_PREFIX).removesuffix(" -->"))


def _render_body(latest: dict[str, Run]) -> str:
    lines = [
        f"{STATE_PREFIX}{json.dumps(latest, sort_keys=True)} -->",
        "",
        "This issue tracks the latest scheduled CI and push-to-main results.",
        "A successful run clears the failure for the event that triggered it.",
        "",
    ]
    for event, name in EVENT_NAMES.items():
        if event in latest:
            run = latest[event]
            lines.append(f"- {name} — [{run['conclusion']}]({run['url']})")
    return "\n".join(lines)


def reconcile(event: str, run: Run) -> None:
    """Apply the result once, with recovery tracked separately for each event."""
    if event not in EVENT_NAMES or run["conclusion"] not in {"failure", "success"}:
        raise ValueError("Expected a scheduled or main-push CI gate result")

    issue = _tracking_issue()
    if issue is None:
        if run["conclusion"] == "success":
            return
        _gh(
            "label",
            "create",
            LABEL,
            "--color",
            "B60205",
            "--description",
            "Tracks failures of CI on main",
            "--force",
        )
        _api(
            "--method",
            "POST",
            ISSUES,
            payload={
                "title": TITLE,
                "labels": [LABEL],
                "body": _render_body({event: run}),
            },
        )
        return

    latest = _read_state(issue["body"])
    previous = latest.get(event)
    if previous is not None and (run["number"], run["attempt"]) <= (
        previous["number"],
        previous["attempt"],
    ):
        return
    latest[event] = run
    failing = any(result["conclusion"] == "failure" for result in latest.values())
    _api(
        "--method",
        "PATCH",
        f"{ISSUES}/{issue['number']}",
        payload={
            "body": _render_body(latest),
            "state": "open" if failing else "closed",
        },
    )


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    server = os.environ["GITHUB_SERVER_URL"]
    run_id = os.environ["GITHUB_RUN_ID"]
    attempt = int(os.environ["GITHUB_RUN_ATTEMPT"])
    reconcile(
        os.environ["GITHUB_EVENT_NAME"],
        {
            "number": int(os.environ["GITHUB_RUN_NUMBER"]),
            "attempt": attempt,
            "url": f"{server}/{repository}/actions/runs/{run_id}/attempts/{attempt}",
            "conclusion": os.environ["CI_GATE_RESULT"],
        },
    )


if __name__ == "__main__":
    main()
