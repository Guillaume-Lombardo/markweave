---
ticket: T110
linear_id: G1L-634
linear_url: https://linear.app/g1lom/issue/G1L-634/t110-remove-legacy-md-converter-configuration-aliases-at-10
status: In Progress
priority: Low
project: Markdown to DOCX and PDF Converter
---

# T110 - Remove legacy MD_CONVERTER_* configuration aliases in 0.8.0

## Objective

Remove the legacy `MD_CONVERTER_*` aliases in the 0.8.0 minor release.

Created from the repository analysis accepted by the owner on 2026-10-09 (section: what to remove or freeze).

## Acceptance criteria

- Remove alias resolution from `src/markweave/config.py` and its tests.
- Add a startup error that names the canonical `MARKWEAVE_*` variable when a legacy variable is present.
- Keep shipped deployment and smoke-test configurations on canonical names.
- Document the break in CHANGELOG and the upgrade guide.

## Dependencies

- None.

## Blocking points

- None. The owner approved removal in 0.8.0 on 2026-11-20.

## Progress

- 2026-11-20: Started implementation after the owner moved alias removal from 1.0 to 0.8.0.
  Removed alias resolution, added a startup error that lists replacements without values, and
  moved the final-image custom-bind smoke to canonical names. Documented the migration and verified
  configuration, CLI startup, and static deployment checks locally. Final rootless image checks
  are pending on Linux.
- 2026-10-09: Created in Linear and mirrored here from the owner-accepted repository analysis.
  Not started.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-634.
