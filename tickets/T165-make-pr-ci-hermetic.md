---
ticket: T165
linear_id: G1L-857
linear_url: https://linear.app/g1lom/issue/G1L-857
status: In Progress
project: Markdown to DOCX and PDF Converter
---

# T165 - Make pull request CI hermetic

## Objective

Keep live release evidence out of routine pull request CI and preserve the release and
adoption gates. Restore main CI alerts after a repository rename.

## Acceptance criteria

- Remove the retired 0.6.0, 0.7.2, and 0.7.4 validator exceptions and their tests. Link the
  archived evidence from the release guide.
- Verify live public alignment on main pushes, Release events, scheduled and manual runs,
  and candidates that change the source release identity or public Compose or quickstart pins.
  Require the exact version transition, deployment agreement, and adoption before subsequent
  changes. Keep `CI / gate` fail-closed when a required check is missing or fails.
- Diagnose the failure of the main CI tracking job in run 45723842884 and cover it with a
  regression test.
- Update the release guide and changelog. Pass the canonical checks and hosted `CI / gate`.

## Dependencies

- T100 (release receipt adoption), T102 (repository rename), and T162 (shared CI alert).

## Progress

- 2026-11-27: Started from `origin/main`. Run 45723842884 recorded an untrusted release
  endpoint redirect and HTTP 307 when GitHub CLI tried to create the tracking issue.
- 2026-11-27: Reproduced both failure paths with regression tests. The light job now selects
  live checks from exact candidate inputs and the alert resolves the canonical issue endpoint
  from the stable GitHub repository ID. The optional workflow policy refactor was deferred.
- 2026-11-27: Rebased after 0.9.0 image adoption. The pull request check compares the synthetic
  merge commit with its first parent and verifies the committed pins against the checked-out
  Compose file and both quickstarts. Each quickstart must match the Compose pair.
