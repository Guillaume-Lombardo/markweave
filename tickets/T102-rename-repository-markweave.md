---
ticket: T102
linear_id: G1L-621
linear_url: https://linear.app/g1lom/issue/G1L-621/t102-rename-the-github-repository-to-markweave
status: In Progress
priority: Low
project: Markdown to DOCX and PDF Converter
---

# T102 - Rename the GitHub repository to markweave

## Objective

Align the repository name with the product name Markweave.

Created from the repository analysis accepted by the owner on 2026-10-09 (section: what to change, item 7).

## Acceptance criteria

- Owner renames the GitHub repository; GitHub redirects remain in place.
- Update project URLs in `pyproject.toml`, README, docs, SECURITY/SUPPORT policies, OCI image labels, CLI help, quickstart clone commands and tests that assert URLs.
- Verify published releases against their original signing identity and bind future releases to the renamed repository.
- The owner adds `markweave` (`release.yml`, `pypi`) as a second PyPI Trusted Publisher. Remove the old publisher only after the first successful release from the renamed repository.
- Keep the PyPI project `markweave`, the GHCR images `md-converter` and `md-converter-web`, and the Linear project name. Do not change `project.version` in this ticket.

## Dependencies

- None.

## Blocking points

- Do not schedule during a release-adoption window.

## Progress

- 2026-10-09: Created in Linear and mirrored here from the owner-accepted repository analysis.
  Not started.
- 2026-11-26: Started on the renamed GitHub repository. The owner retains responsibility for PyPI
  Trusted Publishing.
- 2026-11-26: Updated the live repository references and verified public release alignment through
  the canonical GitHub endpoints. All three 0.8.0 GHCR receipts and attestations verified against
  the published digests and their original signing identity.
- 2026-11-26: The owner added the second PyPI Trusted Publisher for
  `Guillaume-Lombardo/markweave`, workflow `release.yml`, and environment `pypi`. Remove the original
  publisher only after the first successful release from the renamed repository.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-621.
