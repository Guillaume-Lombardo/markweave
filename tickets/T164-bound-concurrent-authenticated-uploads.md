---
ticket: T164
linear_id: G1L-856
linear_url: https://linear.app/g1lom/issue/G1L-856
status: In Progress
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T164 - Bound concurrent authenticated uploads

## Objective

Bound API memory, multipart spool space, and scanner use before forward-conversion jobs reach
persistent quota checks.

## Acceptance criteria

- After authentication and CSRF validation, acquire one of a configurable number of per-process
  upload slots before reading the request body. Reject saturation with a documented HTTP 503 and
  `Retry-After`, without creating a spool, job, or audit record.
- Release capacity after success, validation or scanner failure, disconnect, and cancellation.
  Keep a slot occupied while its scanner or spool I/O is still running or while the response
  retains parsed multipart data. Expire incomplete bodies after a configurable total deadline.
- Measure memory and spool use with concurrent authenticated uploads. Document the default and
  verify that it supports the quickstart and final-image workflows.
- Cover admission and rejection in unit, integration, and final rootless-image tests. Pass the
  canonical checks, changed-line coverage of at least 90%, and the hosted CI gate.
- Document configuration, resource policy, the API error, and the Unreleased changelog. Update
  the OpenAPI artifacts.

## Dependencies

T163 (G1L-854) authenticated streaming and per-upload hard ceilings, and T18 (G1L-328) resource
budgets.

## Progress

- 2026-11-27: Started implementation on `feat/t164-global-upload-budget`.
- 2026-11-27: Chose four upload slots per API process and a 120-second total body deadline.
  The quickstart's 4,100,000-byte hard request ceiling puts at most 16,400,000 bytes of concurrent
  input under the four slots, with room in the 64 MiB backend temporary filesystem. The deadline
  lets a 4.1 MB request finish at approximately 35 kB/s and prevents one incomplete request
  from holding a slot indefinitely.
  Reproduce the pressure measurement with
  `uv run pytest --no-cov tests/integration/sqlite/test_conversion_upload_capacity.py -k pressure -o junit_family=legacy --junitxml=upload-pressure.xml`.
- 2026-11-27: Four authenticated 3,900,000-byte streams occupied 15,600,000 logical spool
  bytes and 15,466,496 bytes in the open temporary files before flush. In the local run, peak
  traced Python allocations were 3.2 MB during spooling and 16.9 MB while all four scans held
  their sources. All spool files were closed by the scan phase. The measurement excludes
  native allocations and socket buffers.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-856.
