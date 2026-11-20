"""Unit tests for the main CI issue lifecycle."""

import json

import pytest
from pytest_mock import MockerFixture

from scripts.ci import main_ci_alert as alert

pytestmark = pytest.mark.unit


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


def test_first_failure_creates_the_labeled_issue(mocker: MockerFixture) -> None:
    api = mocker.patch.object(alert, "_api", return_value=[[]])
    command = mocker.patch.object(alert, "_gh")
    failure = _run(1, "failure")

    alert.reconcile("schedule", failure)

    command.assert_called_once()
    assert command.call_args.args[:3] == ("label", "create", alert.LABEL)
    assert api.call_args.args == ("--method", "POST", alert.ISSUES)
    payload = api.call_args.kwargs["payload"]
    assert payload["title"] == alert.TITLE
    assert payload["labels"] == [alert.LABEL]
    assert alert._read_state(payload["body"]) == {"schedule": failure}
    assert failure["url"] in payload["body"]


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

    alert.reconcile("push", _run(2, "success"))

    api.assert_called_once_with(
        "--paginate",
        "--slurp",
        f"{alert.ISSUES}?state=all&labels={alert.LABEL}&per_page=100",
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
    ],
)
def test_tracking_issue_is_updated_in_place(
    mocker: MockerFixture,
    event: str,
    latest: dict[str, alert.Run],
    run: alert.Run,
    state: str,
) -> None:
    api = mocker.patch.object(alert, "_api", return_value=[[], [_issue(latest)]])

    alert.reconcile(event, run)

    assert api.call_count == 2
    assert api.call_args.args == ("--method", "PATCH", f"{alert.ISSUES}/17")
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

    alert.reconcile("schedule", run)

    api.assert_called_once()


@pytest.mark.parametrize("event", ["pull_request", "workflow_dispatch"])
def test_untracked_events_cannot_write_issues(
    mocker: MockerFixture, event: str
) -> None:
    api = mocker.patch.object(alert, "_api")

    with pytest.raises(ValueError, match="CI gate result"):
        alert.reconcile(event, _run(1, "failure"))

    api.assert_not_called()


def test_update_fails_closed_when_issue_state_is_missing(mocker: MockerFixture) -> None:
    api = mocker.patch.object(
        alert, "_api", return_value=[[_issue({}) | {"body": "Edited manually"}]]
    )

    with pytest.raises(ValueError, match="missing its automation state"):
        alert.reconcile("push", _run(1, "success"))

    api.assert_called_once()


def test_duplicate_tracking_issues_require_manual_resolution(
    mocker: MockerFixture,
) -> None:
    api = mocker.patch.object(
        alert, "_api", return_value=[[_issue({}), _issue({}) | {"number": 18}]]
    )

    with pytest.raises(ValueError, match="Multiple main CI tracking issues"):
        alert.reconcile("push", _run(1, "failure"))

    api.assert_called_once()


def test_entry_point_uses_the_exact_workflow_attempt(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in {
        "GITHUB_REPOSITORY": "example/project",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "987654",
        "GITHUB_RUN_NUMBER": "17",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_EVENT_NAME": "push",
        "CI_GATE_RESULT": "failure",
    }.items():
        monkeypatch.setenv(name, value)
    reconcile = mocker.patch.object(alert, "reconcile")

    alert.main()

    reconcile.assert_called_once_with(
        "push",
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

    assert alert._api("--method", "PATCH", f"{alert.ISSUES}/17", payload=payload) == {
        "number": 17
    }
    assert command.call_args.args[0] == [
        "/usr/bin/gh",
        "api",
        "--method",
        "PATCH",
        f"{alert.ISSUES}/17",
        "--input",
        "-",
    ]
    assert json.loads(command.call_args.kwargs["input"]) == payload
    assert command.call_args.kwargs["check"] is True
