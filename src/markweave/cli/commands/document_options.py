"""Shared command-line flags for Word document structure."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import asdict

from markweave.conversion.document_options import MAX_TOC_DEPTH, DocumentOptions

DOCUMENT_OPTION_NAMES = ("toc", "toc_depth", "number_sections")


def _boolean(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def add_document_arguments(
    parser: argparse.ArgumentParser, action: type[argparse.Action]
) -> None:
    """Register optional overrides while preserving each command's dispatch."""
    parser.add_argument(
        "--toc",
        type=_boolean,
        metavar="true|false",
        action=action,
        help="Enable or disable the table of contents.",
    )
    parser.add_argument(
        "--toc-depth",
        type=int,
        choices=range(1, MAX_TOC_DEPTH + 1),
        action=action,
        help="Maximum heading depth in the table of contents.",
    )
    parser.add_argument(
        "--number-sections",
        type=_boolean,
        metavar="true|false",
        action=action,
        help="Enable or disable heading numbering.",
    )


def selected_options(values: Mapping[str, object]) -> DocumentOptions | None:
    """Return explicitly selected values, including false."""
    fields = {name: values[name] for name in DOCUMENT_OPTION_NAMES if name in values}
    return DocumentOptions(**fields) if fields else None  # ty: ignore[invalid-argument-type]


def supplied_fields(options: DocumentOptions | None) -> dict[str, bool | int]:
    """Omit inherited values on the wire."""
    return (
        {name: value for name, value in asdict(options).items() if value is not None}
        if options is not None
        else {}
    )
