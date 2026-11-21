"""Real-corpus contract for pre-persistence reverse format admission."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from markweave.reversions.detection import admit_reverse_source

pytestmark = pytest.mark.integration

CORPUS = Path(__file__).resolve().parents[3] / "toolchain" / "anydoc" / "corpus"


def test_every_reference_corpus_source_reaches_its_expected_parser_family() -> None:
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    admitted_extensions: set[str] = set()

    for fixture in manifest["files"]:
        source = CORPUS / fixture["path"]
        admission = admit_reverse_source(source.name, source.read_bytes()).admission
        admitted_extensions.add(admission.extension)

    assert admitted_extensions == {
        ".csv",
        ".doc",
        ".docm",
        ".docx",
        ".epub",
        ".odp",
        ".ods",
        ".odt",
        ".pdf",
        ".pot",
        ".pps",
        ".ppsm",
        ".ppsx",
        ".ppt",
        ".pptm",
        ".pptx",
        ".rtf",
        ".xls",
        ".xlsb",
        ".xlsm",
        ".xlsx",
    }
