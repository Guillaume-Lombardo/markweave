---
ticket: T109
linear_id: G1L-633
linear_url: https://linear.app/g1lom/issue/G1L-633/t109-relocate-completed-spikes-and-archive-historical-evidence
status: Done
priority: Low
project: Markdown to DOCX and PDF Converter
---

# T109 - Relocate completed spikes and archive historical evidence

## Objective

Separate production assets from completed qualification spikes and historical evidence.

Created from the repository analysis accepted by the owner on 2026-10-09 (section: what to remove or freeze).

## Acceptance criteria

- Move the `spikes/anydoc` files used in production (reverse-attempt Containerfile, contract, supply-chain and corpus files referenced by tests and scripts) to a production location such as `toolchain/anydoc`; update every reference.
- Move `spikes/composer` fixtures still used by web tests next to those tests; archive the remaining probes.
- Move `docs/evidence/`, `docs/t00-toolchain-validation.md` and `docs/nextjs-migration-architecture.md` under `docs/archive/` with a short index, or delete what the owner no longer needs.
- Image builds, the reverse-attempt smoke, unit, integration, web and documentation tests pass with unchanged image bytes where possible.

## Dependencies

- None.

## Blocking points

- `spikes/anydoc` is referenced by `containers/reverse-attempt/Containerfile`, `scripts/ci/select_domains.py`, `scripts/e2e/run.sh`, smoke scripts and several tests; it cannot simply be deleted.

## Progress

- 2026-10-09: Created in Linear and mirrored here from the owner-accepted repository analysis.
  Not started.
- 2026-11-20: Implemented on `chore/T109-archive-spikes-evidence`. Moved the AnyDoc license,
  contract, inventory, corpus, and smoke probe to `toolchain/anydoc/`. Archived the T69
  feasibility report, qualification image recipe, and measurements in `docs/archive/anydoc/`
  and the T88 Composer probes in `docs/archive/composer/`. The Composer spike generated its
  fixtures outside the repository. Moved the active web preview fixture generator to
  `web/tests/fixtures/composer-preview/`. Archived the historical evidence and T00 and Next.js
  records under `docs/archive/` and added an index. Updated the build, CI selector, scripts, tests,
  and documentation references.
  Dependency sync, Ruff checks, 372 targeted unit, integration, and documentation tests,
  8 broker tests without Podman, and the corpus staging test with GNU coreutils passed.
  The 16 root web tests, 898 frontend tests, production web build, and 8 browser preview cases
  passed. The corpus, packaged license, and RPM snapshot are byte-identical. Stale-path
  search and diff checks passed. A broader local run passed 545 tests and reproduced 23
  platform or dependency failures on the base revision. Type checking reported 18 diagnostics
  for Linux-only APIs on macOS (T154). The canonical broad suites and container image build,
  smoke, and final-image E2E remain for Linux CI.
- 2026-11-21: Merged in #338; CI passed on `main` at `48c2f96`. Closed.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-633.
