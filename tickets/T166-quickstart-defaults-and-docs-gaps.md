---
ticket: T166
linear_id: G1L-858
linear_url: https://linear.app/g1lom/issue/G1L-858
status: In Progress
project: Markdown to DOCX and PDF Converter
---

# T166 - Quickstart defaults and documentation gaps

## Objective

Let users convert ordinary multipage PDFs with the quickstart, explain the Linux requirements
for serverless conversion, and keep current delivery status in the project tracker.

## Acceptance criteria

- The Compose quickstart and local conversion example allow up to 50 PDF pages. The application
  still requires a positive operator-supplied value. The quickstart uses the published image pins.
- README and CLI documentation explain Linux engine isolation and provide the bundled-image
  invocation alongside host usage.
- Section 13 points to Linear and repository ticket mirrors for current delivery status and
  retains its normative coordination rules.
- The changelog records the raised evaluation limit.
- Regression tests, canonical checks on Linux, and the hosted CI gate pass.

## Dependencies

- T18 owns configurable resource limits. T106 defines serverless local conversion.

## Progress

- 2026-11-27: Started from the adopted 0.9.0 quickstart on
  `fix/t166-quickstart-defaults-docs`.
- 2026-11-27: Raised the evaluation limit to 50 pages and added regression coverage for
  Compose settings and bundled PDF conversion. Documented Linux isolation for local conversion
  and removed the dated ticket table once the specification linked to the live tracker.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-858.
