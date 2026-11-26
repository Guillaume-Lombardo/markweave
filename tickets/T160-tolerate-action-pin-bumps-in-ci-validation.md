---
ticket: T160
linear_id: G1L-851
linear_url: https://linear.app/g1lom/issue/G1L-851/t160-tolerate-action-pin-bumps-in-ci-validation
status: Done
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T160 - Tolerate action pin bumps in CI validation

## Objective

Allow routine GitHub Actions version bumps without validator edits while retaining full SHA pinning, version comments, action allowlists, and reviewed workflow behavior.

## Acceptance criteria

- Apply the exact Dependabot PR #356 diff in a local-only commit. The CI validation tests and validator entry point both pass.
- Accept a complete action pin bump. Reject unpinned and short-SHA references, unallowlisted actions, missing or inconsistent version comments, and unreviewed permission or step changes.
- Pass Ruff formatting and lint, ty, and the canonical fast Python suite. Cover at least 90% of changed executable Python lines.
- Pass hosted CI on the implementation pull request.

## Dependencies

- T03 (selective CI and the required gate), delivered.

## Progress

- Replayed the exact PR #356 patch in local-only commit `e8359f7`. All 287 targeted tests and the CI validator entry point passed.
- Verified Ruff formatting and lint, ty, and 95.31% coverage of changed executable validator lines. The changed test lines reached 100% coverage.
- Addressed the independent review finding by rejecting partial bumps within a workflow, including across sub-actions of the same upstream repository. The follow-up review approved the change.

- 2026-11-26: Verified on main: #357 merged as 733fc1d; the main CI on fac2dda (run 45728741404) passed. Dependabot PR #356 (setup-uv 10.4.0) now passes `CI / light` without editing the validator by hand.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-851.
