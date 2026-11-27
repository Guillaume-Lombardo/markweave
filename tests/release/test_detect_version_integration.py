"""Real Git-boundary coverage for protected release retry detection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from scripts.release import public_alignment
from scripts.release.detect_version import (
    VersionTransition,
    detect_repository_transition,
)

pytestmark = pytest.mark.integration


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["/usr/bin/git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_real_git_history_detects_same_version_release_attempt(tmp_path: Path) -> None:
    """An exact protected Git transition can retry an unchanged final version."""
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nversion = "0.3.1"\n', encoding="utf-8")
    _git(tmp_path, "init", "--initial-branch=main")
    _git(tmp_path, "add", "pyproject.toml")
    _git(
        tmp_path,
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release-test@example.invalid",
        "commit",
        "-m",
        "release source",
    )
    before = _git(tmp_path, "rev-parse", "HEAD")

    project.write_text(
        '[project]\nversion = "0.3.1"\n\n[tool.markweave.release]\nattempt = 2\n',
        encoding="utf-8",
    )
    _git(tmp_path, "add", "pyproject.toml")
    _git(
        tmp_path,
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release-test@example.invalid",
        "commit",
        "-m",
        "retry release",
    )
    head = _git(tmp_path, "rev-parse", "HEAD")

    assert detect_repository_transition(
        repository=tmp_path, before=before, head=head
    ) == VersionTransition("0.3.1", "v0.3.1")


def test_pull_request_alignment_uses_the_real_merge_base(
    tmp_path: Path, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(tmp_path, "init", "--initial-branch=main")
    _git(tmp_path, "config", "user.name", "Release Test")
    _git(tmp_path, "config", "user.email", "release-test@example.invalid")
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nversion = "0.4.0"\n', encoding="utf-8")
    (tmp_path / "compose.yaml").write_text(
        "services:\n  markweave:\n"
        f"    image: {public_alignment.IMAGE_REPOSITORY}:0.4.0@sha256:{'a' * 64}\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "pyproject.toml", "compose.yaml")
    _git(tmp_path, "commit", "-m", "aligned release")
    stale_base = _git(tmp_path, "rev-parse", "HEAD")
    topic = _git(
        tmp_path, "commit-tree", "HEAD^{tree}", "-p", stale_base, "-m", "candidate"
    )
    project.write_text('[project]\nversion = "0.5.0"\n', encoding="utf-8")
    _git(tmp_path, "commit", "-am", "release awaiting adoption")
    actual_base = _git(tmp_path, "rev-parse", "HEAD")
    head = _git(
        tmp_path,
        "commit-tree",
        "HEAD^{tree}",
        "-p",
        actual_base,
        "-p",
        topic,
        "-m",
        "PR merge",
    )
    transport = mocker.patch.object(public_alignment, "UrlLibTransport")
    arguments = [
        "--repository",
        str(tmp_path),
        "--event-name",
        "pull_request",
        "--base",
        stale_base,
    ]

    assert public_alignment.main([*arguments, "--head", actual_base]) == 1
    assert "two-parent merge commit" in capsys.readouterr().err

    _git(tmp_path, "switch", "--detach", head)
    assert public_alignment.main([*arguments, "--head", head]) == 1
    assert "adopt published images before other changes" in capsys.readouterr().err
    transport.assert_not_called()
