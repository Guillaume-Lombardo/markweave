---
ticket: T163
linear_id: G1L-854
linear_url: https://linear.app/g1lom/issue/G1L-854/t163-add-flexible-image-and-archive-limits
status: Done
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T163 - Add flexible image and archive limits

## Objective

Follow up on T18 (G1L-328) with proportional raster resizing and explicitly confirmed larger forward-conversion uploads.

## Acceptance criteria

- Resize raster images to fit both dimensions budgets by default with a per-image warning in the job API, browser and CLI. Support strict rejection and enforce a separate pre-decode pixel ceiling.
- Expose configurable soft and hard upload and archive-total limits. Require explicit confirmation within the band, audit accepted overrides with actor, sizes and job ID, and preserve scanning, quotas and member ceilings. Allow operators to disable overrides.
- Cover the decisions, browser confirmation and CLI interaction with unit tests. Verify embedded DOCX image dimensions and upload responses through real integration boundaries and both flows in final rootless-image E2E.
- Pass canonical Python and web checks, at least 90% changed Python line coverage, and hosted CI.
- Record the owner decision and document the settings, clients and ingress requirements.

## Dependencies

T18 (G1L-328) resource budgets.

## Progress

- 2026-11-26: Started implementation on `feat/t163-flexible-image-and-archive-limits`.
- 2026-11-26: Implemented confirmed admission, immutable override auditing, and raster resizing
  with result warnings. Added API, CLI, browser, OpenXML, and final-image regression coverage.
  The preview and conversion worker now use the same raster decoding ceiling.
- 2026-11-26: Restored the restricted reverse-attempt package import and added PNG
  and JPEG header checks. Forward uploads now authenticate before streaming bounded
  multipart data. SQLite tests verify that rejected overrides leave jobs and audit
  records untouched. A global budget for concurrent authenticated uploads remains
  a follow-up.
- 2026-11-26: #363 merged as 9042129; main CI green.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-854.
