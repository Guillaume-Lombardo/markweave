"""Unit tests for the main CI issue lifecycle."""

import json
import subprocess

import pytest
from pytest_mock import MockerFixture

from scripts.ci import main_ci_alert as alert

pytestmark = pytest.mark.unit
REPOSITORY = "example/project"
ISSUES = f"repos/{REPOSITORY}/issues"


def test_creates_tracking_issue_through_canonical_repository_after_rename(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in {
        "GITHUB_REPOSITORY": "example/previous-name",
        "GITHUB_REPOSITORY_ID": "123",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "42",
        "GITHUB_RUN_NUMBER": "2",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_EVENT_NAME": "push",
        "CI_GATE_RESULT": "failure",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("CI_TRACKING_SOURCE", raising=False)
    mocker.patch.object(alert.shutil, "which", return_value="/usr/bin/gh")
    issues = "repos/example/current-name/issues"

    def gh(command, **options):
        match command[1:]:
            case ["api", "repositories/123"]:
                response = {"full_name": "example/current-name"}
            case ["api", "--paginate", "--slurp", query] if query.startswith(issues):
                response = [[]]
            case ["label", "create", *args] if args[-2:] == [
                "--repo",
                "example/current-name",
            ]:
                response = {}
            case ["api", "--method", "POST", endpoint, "--input", "-"]:
                if endpoint != issues:
                    raise subprocess.CalledProcessError(1, command, stderr="HTTP 307")
                payload = json.loads(options["input"])
                assert alert._read_state(payload["body"])["push"]["url"] == (
                    "https://github.com/example/current-name/actions/runs/42/attempts/1"
                )
                response = {"number": 17}
            case _:
                response = [[]]
        return subprocess.CompletedProcess(command, 0, json.dumps(response))

    command = mocker.patch.object(alert.subprocess, "run", side_effect=gh)

    alert.main()

    assert command.call_args.args[0][1:5] == ["api", "--method", "POST", issues]


def _run(number: int, conclusion: str, attempt: int = 1) -> alert.Run:
    return {
        "number": number,
        "attempt": attempt,
        "url": f"https://github.com/example/project/actions/runs/{number}/attempts/{attempt}",
        "conclusion": conclusion,
    }


def _issue(latest: dict[str, alert.Run]) -> dict:
    return {
        "number": 17,
        "title": alert.TITLE,
        "user": {"login": alert.BOT_LOGIN},
        "body": alert._render_body(latest),
    }


@pytest.mark.parametrize(
    ("source", "previous_success"),
    [
        ("schedule", None),
        ("release-qualification", []),
        ("release-qualification", [{"run_number": 1}]),
    ],
)
def test_first_failure_creates_the_labeled_issue(
    mocker: MockerFixture, source: str, previous_success: list[dict[str, int]] | None
) -> None:
    responses = [[[]], {}]
    if previous_success is not None:
        responses.insert(0, {"workflow_runs": previous_success})
    api = mocker.patch.object(alert, "_api", side_effect=responses)
    command = mocker.patch.object(alert, "_gh")
    failure = _run(2, "failure")

    alert.reconcile(REPOSITORY, source, failure)

    command.assert_called_once()
    assert command.call_args.args[:3] == ("label", "create", alert.LABEL)
    assert api.call_args.args == ("--method", "POST", ISSUES)
    payload = api.call_args.kwargs["payload"]
    assert payload["title"] == alert.TITLE
    assert payload["labels"] == [alert.LABEL]
    assert alert._read_state(payload["body"]) == {source: failure}
    assert alert.TRACKING_SOURCES[source] in payload["body"]
    assert failure["url"] in payload["body"]


@pytest.mark.parametrize(
    "latest",
    [None, {"push": _run(3, "success")}, {"release-qualification": _run(1, "success")}],
)
def test_older_dry_run_failure_cannot_raise_an_alert_after_newer_success(
    mocker: MockerFixture, latest: dict[str, alert.Run] | None
) -> None:
    api = mocker.patch.object(
        alert,
        "_api",
        side_effect=[
            {"workflow_runs": [{"run_number": 2}]},
            [[_issue(latest)] if latest is not None else []],
        ],
    )
    command = mocker.patch.object(alert, "_gh")

    alert.reconcile(REPOSITORY, "release-qualification", _run(1, "failure", attempt=2))

    api.assert_called_once_with(
        f"repos/{REPOSITORY}/actions/workflows/release-qualification-dry-run.yml/runs"
        "?branch=main&status=success&per_page=1"
    )
    command.assert_not_called()


def test_green_run_without_an_owned_issue_does_nothing(mocker: MockerFixture) -> None:
    unrelated = _issue({})
    api = mocker.patch.object(
        alert,
        "_api",
        return_value=[
            [unrelated | {"user": {"login": "maintainer"}}],
            [unrelated | {"pull_request": {}}, unrelated | {"title": "Other alert"}],
        ],
    )
    command = mocker.patch.object(alert.subprocess, "run")

    alert.reconcile(REPOSITORY, "push", _run(2, "success"))

    api.assert_called_once_with(
        "--paginate",
        "--slurp",
        f"{ISSUES}?state=all&labels={alert.LABEL}&per_page=100",
    )
    command.assert_not_called()


@pytest.mark.parametrize(
    ("event", "latest", "run", "state"),
    [
        ("push", {"schedule": _run(2, "failure")}, _run(3, "success"), "open"),
        ("schedule", {"schedule": _run(2, "failure")}, _run(3, "success"), "closed"),
        ("schedule", {"schedule": _run(2, "failure")}, _run(2, "success", 2), "closed"),
        ("push", {"push": _run(2, "failure")}, _run(3, "success"), "closed"),
        ("push", {"push": _run(2, "failure")}, _run(3, "failure"), "open"),
        ("push", {"push": _run(2, "success")}, _run(3, "failure"), "open"),
        (
            "push",
            {"release-qualification": _run(2, "failure")},
            _run(3, "success"),
            "open",
        ),
        (
            "release-qualification",
            {"push": _run(3, "success")},
            _run(1, "failure"),
            "open",
        ),
        (
            "release-qualification",
            {"release-qualification": _run(2, "failure"), "push": _run(3, "success")},
            _run(3, "success"),
            "closed",
        ),
        (
            "release-qualification",
            {"schedule": _run(4, "failure")},
            _run(4, "success"),
            "open",
        ),
    ],
)
def test_tracking_issue_is_updated_in_place(
    mocker: MockerFixture,
    event: str,
    latest: dict[str, alert.Run],
    run: alert.Run,
    state: str,
) -> None:
    responses = [[[], [_issue(latest)]], {}]
    if event == "release-qualification" and run["conclusion"] == "failure":
        responses.insert(0, {"workflow_runs": []})
    api = mocker.patch.object(alert, "_api", side_effect=responses)

    alert.reconcile(REPOSITORY, event, run)

    assert api.call_count == len(responses)
    assert api.call_args.args == ("--method", "PATCH", f"{ISSUES}/17")
    payload = api.call_args.kwargs["payload"]
    assert payload["state"] == state
    assert alert._read_state(payload["body"]) == latest | {event: run}


@pytest.mark.parametrize("run", [_run(2, "failure", 3), _run(3, "failure", 2)])
def test_older_runs_and_duplicate_attempts_are_ignored(
    mocker: MockerFixture, run: alert.Run
) -> None:
    api = mocker.patch.object(
        alert, "_api", return_value=[[_issue({"schedule": _run(3, "success", 2)})]]
    )

    alert.reconcile(REPOSITORY, "schedule", run)

    api.assert_called_once()


@pytest.mark.parametrize("event", ["pull_request", "workflow_dispatch"])
def test_untracked_events_cannot_write_issues(
    mocker: MockerFixture, event: str
) -> None:
    api = mocker.patch.object(alert, "_api")

    with pytest.raises(ValueError, match="CI gate result"):
        alert.reconcile(REPOSITORY, event, _run(1, "failure"))

    api.assert_not_called()


def test_update_fails_closed_when_issue_state_is_missing(mocker: MockerFixture) -> None:
    api = mocker.patch.object(
        alert, "_api", return_value=[[_issue({}) | {"body": "Edited manually"}]]
    )

    with pytest.raises(ValueError, match="missing its automation state"):
        alert.reconcile(REPOSITORY, "push", _run(1, "success"))

    api.assert_called_once()


def test_duplicate_tracking_issues_require_manual_resolution(
    mocker: MockerFixture,
) -> None:
    api = mocker.patch.object(
        alert, "_api", return_value=[[_issue({}), _issue({}) | {"number": 18}]]
    )

    with pytest.raises(ValueError, match="Multiple main CI tracking issues"):
        alert.reconcile(REPOSITORY, "push", _run(1, "failure"))

    api.assert_called_once()


@pytest.mark.parametrize(
    ("event", "tracking_source", "expected_source"),
    [
        ("push", None, "push"),
        ("schedule", "release-qualification", "release-qualification"),
        ("workflow_dispatch", "release-qualification", "release-qualification"),
    ],
)
def test_entry_point_uses_the_exact_workflow_attempt(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    tracking_source: str | None,
    expected_source: str,
) -> None:
    for name, value in {
        "GITHUB_REPOSITORY_ID": "123",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "987654",
        "GITHUB_RUN_NUMBER": "17",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_EVENT_NAME": event,
        "CI_GATE_RESULT": "failure",
    }.items():
        monkeypatch.setenv(name, value)
    if tracking_source is None:
        monkeypatch.delenv("CI_TRACKING_SOURCE", raising=False)
    else:
        monkeypatch.setenv("CI_TRACKING_SOURCE", tracking_source)
    mocker.patch.object(alert, "_api", return_value={"full_name": REPOSITORY})
    reconcile = mocker.patch.object(alert, "reconcile")

    alert.main()

    reconcile.assert_called_once_with(
        REPOSITORY,
        expected_source,
        {
            "number": 17,
            "attempt": 2,
            "url": "https://github.com/example/project/actions/runs/987654/attempts/2",
            "conclusion": "failure",
        },
    )


def test_issue_payload_is_passed_as_json_on_standard_input(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(alert.shutil, "which", return_value="/usr/bin/gh")
    command = mocker.patch.object(alert.subprocess, "run")
    command.return_value.stdout = json.dumps({"number": 17})
    payload = {"body": "First line\nSecond line"}

    assert alert._api("--method", "PATCH", f"{ISSUES}/17", payload=payload) == {
        "number": 17
    }
    assert command.call_args.args[0] == [
        "/usr/bin/gh",
        "api",
        "--method",
        "PATCH",
        f"{ISSUES}/17",
        "--input",
        "-",
    ]
    assert json.loads(command.call_args.kwargs["input"]) == payload
    assert command.call_args.kwargs["check"] is True
