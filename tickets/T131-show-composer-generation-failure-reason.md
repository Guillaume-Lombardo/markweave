---
ticket: T131
linear_id: G1L-684
linear_url: https://linear.app/g1lom/issue/G1L-684/t131-show-the-stable-failure-reason-of-composer-generations
status: Backlog
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T131 - Show the stable failure reason of Composer generations

## Objective

When a Composer generation fails, tell the author why, using the conversion job's existing stable
error code and message, instead of only a failed status.

Found on 2026-10-11 on the docker-box test instance (candidate `00a98ec`). A DOCX generation failed
at validation with `error_code=validation` and `error_message="Markdown input contains raw HTML."`
because the draft contained a path such as `/opt/.../stacks/<stack>/...` outside a code span.
`ComposerGenerationResponse` exposes only `status`, so the workspace could not show the reason or
how to fix it.

## Acceptance criteria

- The Composer generation API exposes the failed job's stable error code and user-safe message (no
  internal details), consistent with the existing conversion job error contract, and OpenAPI is
  updated.
- The Composer workspace shows that reason on a failed generation, with actionable guidance for
  validation failures (for example, raw HTML: wrap literal angle-bracket text in a code span or
  escape it).
- Authorization is unchanged: only the generation owner sees the reason.
- Unit, integration and final-image E2E tests cover a validation-failed generation (raw HTML) in
  both profiles.

## Dependencies

- None.

## Blocking points

- None known. Whether Composer should also warn about raw HTML before generation is out of scope
  unless the owner decides otherwise; T105 (sanitized inline HTML allowlist) does not cover
  arbitrary tags such as `<stack>`.
- Composer is frozen by D16. Work on this ticket is admissible only as a bug fix under the freeze
  rule of section 3.7 of the product specification.

## Progress

- 2026-10-11: Created in Linear.
- 2026-11-25: Mirrored here by T161; it was missing from the repository. Status unchanged
  (Backlog).

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-684.
