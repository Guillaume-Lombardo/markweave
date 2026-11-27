"""Pinned document engines preserve native Word structure and populate PDF indexes."""

import os
import pwd
import stat
from dataclasses import replace
from pathlib import Path

import pytest

from markweave.conversion.document_options import DocumentOptions
from markweave.conversion.pandoc import PandocConfig, PandocDocxConverter
from markweave.conversion.service import DocxConversionService
from tests.golden.document_structure import (
    DOCUMENT_STRUCTURE,
    assert_populated_pdf_toc,
    assert_structure_docx,
)
from tests.integration.document_engines.test_libreoffice_pdf import (
    _converter,
    _reference_docx,
    _trace,
    _workspace,
)

pytestmark = [pytest.mark.integration, pytest.mark.requires_pandoc]


def _convert(workspace: Path, reference: bytes, options: DocumentOptions) -> bytes:
    markdown = "---\ntoc: true\n---\n\n" + Path(DOCUMENT_STRUCTURE).read_text(
        encoding="utf-8"
    )
    service = DocxConversionService(
        PandocDocxConverter(PandocConfig("pandoc", 30.0, 2.0, workspace), os.environ)
    )
    return service.convert(markdown, reference, document_options=options)


@pytest.mark.parametrize("enabled", [False, True])
def test_docx_structure_matches_openxml_golden(tmp_path: Path, enabled: bool) -> None:
    docx = _convert(tmp_path, _reference_docx(), DocumentOptions(enabled, 1, enabled))
    assert_structure_docx(docx, toc=enabled, numbered=enabled)


@pytest.mark.requires_libreoffice
def test_pdf_structure_has_populated_toc_with_page_numbers(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    reference = _reference_docx()
    options = DocumentOptions(True, 1, True)
    docx = _convert(workspace, reference, options)
    assert_structure_docx(docx, toc=True, numbered=True)
    socket_seen = False
    pipe_root = Path("/tmp")  # noqa: S108 - inspect LibreOffice's fixed pipe location
    unregistered_uid = os.environ.get("ENGINE_EXPECT_UNREGISTERED_UID") == "1"
    if unregistered_uid:
        with pytest.raises(KeyError):
            pwd.getpwuid(os.getuid())

    def inspect_pipe() -> bool:
        nonlocal socket_seen
        if unregistered_uid:
            for socket in pipe_root.glob("OSL_PIPE_markweave_*/uno"):
                if socket.is_socket():
                    assert stat.S_IMODE(socket.parent.stat().st_mode) == 0o700
                    socket_seen = True
        return False

    result = _converter(workspace).convert(
        docx, replace(_trace(reference), document_options=options), inspect_pipe
    )
    assert result.manifest.document_options == options
    assert_populated_pdf_toc(result.pdf)
    if unregistered_uid:
        assert socket_seen
        assert not list(pipe_root.glob("OSL_PIPE_markweave_*"))
