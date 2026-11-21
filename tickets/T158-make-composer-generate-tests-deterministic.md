---
ticket: T158
linear_id: G1L-779
linear_url: https://linear.app/g1lom/issue/G1L-779/t158-make-composer-generate-tests-deterministic
status: Done
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T158 - Make Composer Generate tests deterministic

## Objective

Remove the intermittent failures in the two Composer workspace tests that click Generate after
editing Markdown. The failures were reported in `CI / light`, including
[PR #348, job 136665357545](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/44845884299/job/136665357545).

## Acceptance criteria

- Reproduce and explain the timing dependency in the two tests. Check other Generate clicks in
  the same files for the same dependency.
- Make the tests wait for Generate to be available while preserving their assertions about
  saving, publication, conversion, and recovery. Preserve Composer behavior and the existing
  test deadlines.
- Report failure counts from repeated runs before and after, including under CPU load, and run
  the complete web workspace check.

## Dependencies

- None. T136 is related prior work on template catalog readiness. T155 permits test-stability
  fixes during the Composer freeze.

## Progress

- 2026-11-21: Started on `fix/flaky-composer-generate-tests` from `origin/main` at `4e45570`.
- 2026-11-21: Root cause: Generate stays disabled until the template catalog resolves, and both
  tests clicked it as soon as the editor appeared, so a slow catalog turned the click into a no-op.
  Both tests now wait for Generate to be enabled before each click, like the neighboring Generate
  tests. With the catalog delayed by 200 ms, both tests failed before the change and passed after
  it. The complete web Vitest suite passed (898 tests).
- 2026-11-21: Merged in #349; CI passed on `main` at `6548266`. Closed.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-779.
