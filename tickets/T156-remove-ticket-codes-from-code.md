---
ticket: T156
linear_id: G1L-777
linear_url: https://linear.app/g1lom/issue/G1L-777
status: Done
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T156 - Remove ticket codes from code

## Objective

Name code and tests for the behavior they implement or verify. Batch repository mirror updates
for closed tickets while keeping Linear current.

## Acceptance criteria

- Rename ticket-coded modules, tests, and fixture paths under `src/` and `tests/`, along with
  the PDF golden generator. Update their imports, configuration, CI selectors, and documentation
  references. Preserve Alembic migration files and revision IDs.
- Describe behavior in source comments and docstrings without ticket codes. Apply mechanical
  edits to test names, comments, and docstrings in tests and scripts. Preserve persisted values
  and assertions about documentation and ticket content.
- Update `AGENTS.md` and the ticket synchronization skill so mirror closures can be batched
  into the next functional PR or a periodic sync PR. Update Linear immediately once the work
  is verified on `main`.
- Preserve runtime behavior, public contracts, and the bytes of the OpenAPI and HTTP fixtures.

## Dependencies

- Merge after T107 and T110, which delete or rewrite many of the same files.

## Progress

- 2026-11-21: Renamed ticket-coded paths and updated their consumers. Rewrote comments,
  docstrings, and test names around the behavior they describe and documented batched closures.
  Preserved migration history and the OpenAPI descriptions generated from the `FormatFamily`,
  `ReverseOutputMode`, and `TemplateStatus` docstrings. The persisted cleanup kind
  `composer_t91_audit` is retained for existing records.
- 2026-11-21: Ruff, ty, CI validation, and the targeted tests passed. On macOS, the default suite
  matched `main` with 6,292 passed, 120 skipped, 136 deselected, and the same 114 Docker setup
  errors. The OpenAPI artifacts and HTTP snapshots matched byte for byte.
- 2026-11-21: Merged in #347; CI passed on `main` at `49f2f1e`. Closed.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-777.
