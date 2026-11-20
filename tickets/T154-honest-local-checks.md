---
ticket: T154
linear_id: G1L-775
linear_url: https://linear.app/g1lom/issue/G1L-775/t154-make-local-checks-honest-on-non-linux-hosts
status: Backlog
priority: High
project: Markdown to DOCX and PDF Converter
---

# T154 - Make local checks honest on non-Linux hosts

## Objective

Make the canonical local checks report actionable results on macOS. Type-check against the Linux
runtime and keep portable tests runnable on development hosts.

## Acceptance criteria

- `uv run ty check` targets Linux on every host and reports no diagnostics on macOS.
- Register `requires_linux` and skip marked tests with an explicit reason on non-Linux hosts.
  Apply the marker only where Linux kernel, userland, or distribution artifacts are required.
  Keep portable tests runnable by correcting their fixtures.
- The default macOS test command reports only unavailable PostgreSQL and S3 services. Document
  how to run the full suite on Linux.
- Linux CI retains its existing test selections. The marked tests run on Linux.

## Dependencies

- T153 for the CI baseline.

## Progress

- 2026-11-20: Started from `main` at `e9c25b9`. The baseline type check reproduced 18
  Linux API diagnostics on macOS.
- 2026-11-20: Registered the Linux marker and kept portable Unix, HTTPS, and template API
  scenarios in the default selection. Added a subprocess regression test for the skip policy.
  Verified all 25 runner jobs use Ubuntu and both reusable-workflow calls stay local.
  The CI validator and existing marker expressions accept the test changes.
- 2026-11-20: On Linux x86-64, all 138 Linux-marked cases and 146 targeted broker,
  Composer, and template cases passed after dependency synchronization.
- 2026-11-20: The canonical macOS command moved from 6,428 passed, 193 failed, and 153 errors
  on main to 6,536 passed, 138 Linux skips, and 114 setup errors. All setup errors came from
  the unavailable local Docker service used for PostgreSQL and S3. The final run reached
  94.16% total and 90.01% branch coverage. Ruff, ty, CI policy validation, and 16 web tests
  passed. The complete engine-backed suite requires Linux with the document engines and services.

## Synchronization

G1L-775 is in Backlog with Medium priority. This mirror records the requested High priority.
Linear updates are deferred.
