"""Structural golden assertions for the document-structure corpus."""

import io
import re
import zipfile

from defusedxml.ElementTree import fromstring
from pypdf import PdfReader

from tests.golden.openxml import WORD_NAMESPACE

DOCUMENT_STRUCTURE = "tests/corpus/document-structure/document.md"


def assert_structure_docx(content: bytes, *, toc: bool, numbered: bool) -> None:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        document = fromstring(archive.read("word/document.xml"))
    namespace = {"w": WORD_NAMESPACE}
    fields = [node.text for node in document.findall(".//w:instrText", namespace)]
    assert fields == ([r'TOC \o "1-1" \h \z \u'] if toc else [])
    pages = document.findall(".//w:br[@w:type='page']", namespace)
    assert len(pages) == 1
    heading = next(
        paragraph
        for paragraph in document.findall(".//w:p", namespace)
        if any(
            node.text == "Last Heading"
            for node in paragraph.findall(".//w:t", namespace)
        )
    )
    assert [node.text for node in heading.findall(".//w:t", namespace)] == (
        ["2", "Last Heading"] if numbered else ["Last Heading"]
    )


def assert_populated_pdf_toc(content: bytes) -> None:
    pages = PdfReader(io.BytesIO(content), strict=True).pages
    assert len(pages) == 2
    first = pages[0].extract_text()
    assert "Table of Contents" in first
    assert re.search(r"First Heading[\s.]+1\b", first)
    assert re.search(r"Last Heading[\s.]+2\b", first)
    assert first.count("Inset Detail") == 1
    assert "Last Heading" in pages[1].extract_text()
