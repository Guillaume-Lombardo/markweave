---
ticket: T162
linear_id: G1L-853
linear_url: https://linear.app/g1lom/issue/G1L-853/t162-run-weekly-release-qualification-without-publication
status: Done
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T162 - Run weekly release qualification without publication

## Objective

Run the release's container qualification on main every week and on manual dispatch. Detect
upstream download, checksum, and Critical-vulnerability drift before publication.

## Acceptance criteria

- Use the release's cold image builds, fresh Grype database, Critical-vulnerability gate,
  supply-chain checks, and exact-image smoke and E2E jobs.
- Prove that the dry-run has no publication path and that workflow validation rejects publication
  permissions or steps. Report failures through the existing main CI tracking issue.
- Pass Ruff formatting and lint, ty, and the canonical fast suite with at least 90% coverage of
  changed Python lines.
- Dispatch on the PR branch if permitted. Record the run and result, or document the dispatch
  restriction.
- Pass hosted PR CI.

## Dependencies

- T134 (reusable release qualification) and the main CI failure tracker.
- T160 must merge before the canonical policy digests are finalized.

## Progress

- Started on `chore/t162-weekly-release-dry-run` from `origin/main`.
- Reused release qualification and the main CI tracking issue. The workflow policy rejects
  publication permissions and steps and accepts routine action pin bumps.
- Regression tests cover shared issue updates and stale dry-run retries after a newer success.
- Qualification and reporting run on `main`. The first manual run requires the workflow to
  exist on the default branch.

- 2026-11-26: Verified on main: #360 merged as dfaee75. The first dispatched dry-run on main (run 45723845585) passed all eight jobs: stage, smoke, supply-chain, four E2E jobs and failure tracking. Nothing was published.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-853.
