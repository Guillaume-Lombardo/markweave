"""Shell-level coverage for the installed Markweave console executable."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from markweave.version import VERSION

pytestmark = [pytest.mark.integration, pytest.mark.light_coverage]


def test_installed_console_script_reports_version_and_login_argument_errors() -> None:
    """The console wrapper exposes the implemented authentication parser."""
    executable = Path(sys.executable).with_name("markweave")
    version = subprocess.run(
        (str(executable), "--version"), capture_output=True, check=False, text=True
    )
    assert version.returncode == 0
    assert version.stdout == f"markweave {VERSION}\n"
    assert version.stderr == ""

    invalid_login = subprocess.run(
        (str(executable), "--json", "login"),
        capture_output=True,
        check=False,
        text=True,
    )
    assert invalid_login.returncode == 2
    assert invalid_login.stdout == ""
    assert "--url" in invalid_login.stderr


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        (("serve",), "invalid_configuration"),
        (("convert", "unused.md", "--local"), "local_configuration_invalid"),
    ],
)
def test_installed_console_script_reports_removed_environment_alias(
    monkeypatch: pytest.MonkeyPatch, arguments: tuple[str, ...], code: str
) -> None:
    monkeypatch.setenv("MD_CONVERTER_PORT", "private-value")
    executable = Path(sys.executable).with_name("markweave")

    result = subprocess.run(
        (str(executable), "--json", *arguments),
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "private-value" not in result.stderr
    assert json.loads(result.stderr)["error"] == {
        "code": code,
        "message": (
            "Legacy configuration variables were removed. "
            "Rename MD_CONVERTER_PORT -> MARKWEAVE_PORT."
        ),
    }
