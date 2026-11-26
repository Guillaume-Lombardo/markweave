---
ticket: T161
linear_id: G1L-852
linear_url: https://linear.app/g1lom/issue/G1L-852/t161-synchronize-project-tracking-after-the-council-review
status: Done
priority: High
project: Markdown to DOCX and PDF Converter
---

# T161 - Synchronize project tracking after the council review

## Objective

Remove the tracking drift found by the three-model council review. Apply the owner decisions of
2026-11-25 to Linear and the ticket mirrors, refresh the open-ticket table (section 13) and the
Composer programme text (section 14) of the product specification, and align the release-recovery
contract of section 11 with the tested workflow. Documentation and tracking only: no product code.

## Owner decisions applied

- T134: Done. Merged in #315; the first release after merge (0.8.0) qualified and published after
  two failed attempts that left no tag, Release, or PyPI upload.
- T23, T63, T95: Done in Linear already (#264, #265, #272); the mirrors catch up. T91 is Done.
- T74: Canceled. T107 (#340) removed the Kubernetes reverse backend.
- T92, T93: Canceled. Frozen by D16; reopening needs a new owner decision.
- Backlog triage: cancel T115, T116, T117, T119, T122, T123, T125, T126, T127 unless a recorded
  specification decision approves the ticket. Keep T105, T111, T112, T113, T114, T118, T120, T121,
  T145 (without the obsolete Kubernetes-attester scope), T148, and T149.
- T102 stays open; a separate lot implements it.
- Section 11: manual recovery may publish only the exact retained, qualified, digest-verified bytes
  and never rebuilds.
- AGENTS.md: no feature work starts or merges while main CI is red, except the fix.

## Acceptance criteria

- Every touched mirror matches Linear, with a progress note dated 2026-11-25.
- Section 13 lists only genuinely open tickets; no mirror keeps a stale In Progress status.
- `uv run ruff format --check .`, `uv run ruff check .`, the documentation, ticket, and language
  tests, and the fast local suite pass.
- Hosted CI is green.

## Dependencies

- None. Runs in parallel with T159 and T160 without touching their files.

## Progress

- 2026-11-25: Created in Linear and mirrored here. Started on branch
  `docs/t161-synchronize-tracking` from `origin/main` `2ceab70`.
- 2026-11-25: Applied in Linear and the mirrors.
  - Done: T134, with the 0.8.0 release evidence and per-job durations. Mirrors of T23, T63, and
    T95 now match Linear.
  - Canceled: T74, T92, T93, T119, T123, T125, T126, T127, each with a one-line reason.
  - Kept because a recorded decision approves them: T115 (D8), T116 (D9), T117 (D10), and
    T122 (D11).
  - T145 no longer covers the removed Kubernetes attester transport.
  - Linear-only T131 (G1L-684) and T132 (G1L-685) had no mirror; both are now mirrored as
    Backlog.
- 2026-11-25: Updated the product specification: D13 to D16, section 11 manual recovery, the
  section 13 table, and the section 14 T74 and Composer programme text. Updated `docs/index.md`,
  `docs/delivery-history.md`, and AGENTS.md (red-main rule).
- Not changed: Linear reopened T18 (G1L-328) to In Progress on 2026-10-23 without a recorded reason,
  while its mirror is Done. The owner must decide which surface is right.

- 2026-11-26: Verified on main: #358 merged as 6183b28; the main CI on fac2dda (run 45728741404) passed.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-852.
