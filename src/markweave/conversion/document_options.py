"""Template defaults and submission overrides for Word document structure."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

MAX_TOC_DEPTH = 6


@dataclass(frozen=True, slots=True)
class DocumentOptions:
    """Optional Word document settings, with unset fields inherited at submission."""

    toc: bool | None = None
    toc_depth: int | None = None
    number_sections: bool | None = None

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (self.toc, self.number_sections)
            if value is not None
        ):
            raise ValueError("Table of contents and section numbering must be boolean")
        if self.toc_depth is not None and (
            type(self.toc_depth) is not int or not 1 <= self.toc_depth <= MAX_TOC_DEPTH
        ):
            raise ValueError("Table of contents depth must be between 1 and 6")

    def resolve(self, defaults: DocumentOptions) -> DocumentOptions:
        """Apply individual overrides, including explicit false values."""
        return DocumentOptions(
            self.toc if self.toc is not None else defaults.toc,
            self.toc_depth if self.toc_depth is not None else defaults.toc_depth,
            self.number_sections
            if self.number_sections is not None
            else defaults.number_sections,
        )

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def pandoc_arguments(self) -> list[str]:
        """Translate resolved document settings into fixed Pandoc switches."""
        arguments = []
        if self.toc:
            arguments.extend(
                (
                    "--toc",
                    f"--toc-depth={self.toc_depth or DEFAULT_DOCUMENT_OPTIONS.toc_depth}",
                )
            )
        elif self.toc is False:
            arguments.append("--metadata=toc:false")
        if self.number_sections:
            arguments.append("--number-sections")
        return arguments

    @classmethod
    def from_json(cls, content: str) -> DocumentOptions:
        return cls(**json.loads(content))


DEFAULT_DOCUMENT_OPTIONS = DocumentOptions(
    toc=False, toc_depth=3, number_sections=False
)
