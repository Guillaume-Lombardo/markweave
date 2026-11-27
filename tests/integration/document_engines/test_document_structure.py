"""Pinned document engines preserve native Word structure and populate PDF indexes."""

import os
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
    markdown = Path(DOCUMENT_STRUCTURE).read_text(encoding="utf-8")
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
    result = _converter(workspace).convert(
        docx, replace(_trace(reference), document_options=options)
    )
    assert result.manifest.document_options == options
    assert_populated_pdf_toc(result.pdf)
