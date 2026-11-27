"""Track failed main CI runs in a single GitHub issue."""

import json
import os
import shutil
import subprocess
from typing import Any, TypedDict

TITLE = "Main CI is failing"
LABEL = "ci-main-failure"
BOT_LOGIN = "github-actions[bot]"
STATE_PREFIX = "<!-- main-ci-state "
DRY_RUN_SOURCE = "release-qualification"
TRACKING_SOURCES = {
    "schedule": "Scheduled CI",
    "push": "Push to main",
    DRY_RUN_SOURCE: "Release qualification dry-run",
}


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


def _tracking_issue(issues: str) -> dict[str, Any] | None:
    pages = _api(
        "--paginate", "--slurp", f"{issues}?state=all&labels={LABEL}&per_page=100"
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
        "This issue tracks scheduled CI, push-to-main CI, and release qualification.",
        "A successful run clears the failure for the corresponding check.",
        "",
    ]
    for source, name in TRACKING_SOURCES.items():
        if source in latest:
            run = latest[source]
            lines.append(f"- {name} — [{run['conclusion']}]({run['url']})")
    return "\n".join(lines)


def reconcile(repository: str, source: str, run: Run) -> None:
    """Apply the result once, with recovery tracked separately for each source."""
    if source not in TRACKING_SOURCES or run["conclusion"] not in {
        "failure",
        "success",
    }:
        raise ValueError("Expected a tracked main CI gate result")

    if source == DRY_RUN_SOURCE and run["conclusion"] == "failure":
        successful_runs = _api(
            f"repos/{repository}/actions/workflows/release-qualification-dry-run.yml/runs"
            "?branch=main&status=success&per_page=1"
        )["workflow_runs"]
        if any(result["run_number"] > run["number"] for result in successful_runs):
            return

    issues = f"repos/{repository}/issues"
    issue = _tracking_issue(issues)
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
            "--repo",
            repository,
        )
        _api(
            "--method",
            "POST",
            issues,
            payload={
                "title": TITLE,
                "labels": [LABEL],
                "body": _render_body({source: run}),
            },
        )
        return

    latest = _read_state(issue["body"])
    previous = latest.get(source)
    if previous is not None and (run["number"], run["attempt"]) <= (
        previous["number"],
        previous["attempt"],
    ):
        return
    latest[source] = run
    failing = any(result["conclusion"] == "failure" for result in latest.values())
    _api(
        "--method",
        "PATCH",
        f"{issues}/{issue['number']}",
        payload={
            "body": _render_body(latest),
            "state": "open" if failing else "closed",
        },
    )


def main() -> None:
    # The checkout and event can still refer to an old name after a rename.
    # Resolve the stable repository ID before any issue or label mutation.
    repository_id = int(os.environ["GITHUB_REPOSITORY_ID"])
    repository = _api(f"repositories/{repository_id}")["full_name"]
    server = os.environ["GITHUB_SERVER_URL"]
    run_id = os.environ["GITHUB_RUN_ID"]
    attempt = int(os.environ["GITHUB_RUN_ATTEMPT"])
    reconcile(
        repository,
        os.environ.get("CI_TRACKING_SOURCE") or os.environ["GITHUB_EVENT_NAME"],
        {
            "number": int(os.environ["GITHUB_RUN_NUMBER"]),
            "attempt": attempt,
            "url": f"{server}/{repository}/actions/runs/{run_id}/attempts/{attempt}",
            "conclusion": os.environ["CI_GATE_RESULT"],
        },
    )


if __name__ == "__main__":
    main()
