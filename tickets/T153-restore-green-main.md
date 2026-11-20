---
ticket: T153
linear_id: G1L-774
linear_url: https://linear.app/g1lom/issue/G1L-774/t153-restore-a-green-main-stable-image-package-inventory-dependency
status: In Progress
priority: High
project: Markdown to DOCX and PDF Converter
---

# T153 - Restore a green main

## Objective

Keep CI working as the live UBI repositories publish RPM updates, qualify the pending dependency
updates, and surface failures on the default branch.

## Evidence

- Scheduled CI failed on 2026-10-25, 2026-11-01, 2026-11-08 and 2026-11-15 without an alert.
  The last three runs failed verification of the exact installed-RPM hash after DNF resolved newer
  packages from the live UBI repositories.
- Run 40176463243 reported CVE-2026-114406 in the backend and reverse-attempt CA bundles and
  GHSA-cg2g-xh64-v4q7 in the backend Mermaid graph's DOMPurify.
- PR #331 run 40270935434 rejected updated action pins because the reviewed workflow digests and
  associated test inputs still described the old versions. Its supply-chain job reported the same
  findings as the scheduled run.
- PR #335 run 42562309731 rejected the Mermaid lockfile checksum and component version pins. Its
  image build also hit the RPM hash failure.
- PR #336 run 43804611302 exposed the removal of pypdf's global stream-length setting, stale
  dependency and PDFium assertions, and two renamed type-check rule suppressions.

## Acceptance criteria

- The digest-pinned backend image records full RPM evidence and accepts version drift only when
  the installed package, architecture, and license rows still match the reviewed baseline.
- The backend and reverse-attempt images update the UBI CA bundle. The Mermaid graph resolves
  DOMPurify 3.4.17 or later. The existing image vulnerability gate remains active.
- Adopt the locked Python group from #336, use pypdf's scoped API to preserve PDF limits, and verify
  the dependency matrix. Integrate #331 and #335 or record any deferred update and its blocker.
- A scheduled or push-to-main CI failure opens or updates one labeled issue. A green result
  clears its own event's failure, and the issue closes when all tracked events are green. Issue
  writes are confined to the dedicated main-only job. Unit tests exercise failure and recovery.
- Run canonical host checks and targeted tests. The pull request is the qualification point for
  the image build, supply-chain checks, document engines, and final-image E2E.

## Dependencies

- T00 and T20 for toolchain inputs, final-image evidence, and supply-chain verification.
- T11 for Mermaid and PDF fidelity, T18 for PDF resource bounds, and T22 for CI policy.
- T154 tracks the independent macOS validation gap.

## Progress

- 2026-11-20: Started from main at `305734b`. Derived the approved package, architecture,
  and license rows from the published 0.7.5 backend image after verifying its manifest, layer,
  and the 549-row legacy inventory digest `92063803ffaf534054d2d198abd814d08f22626a4238cb126e03376fb102a99e`.
  The baseline preserves the multiplicity of the three RPM signing-key records.
- 2026-11-20: Adopted #331, #335, and #336. Compared the 35 UBI package and license rows
  from the latest failed build and the CA update with current Red Hat repository metadata.
  The updated CA package is `0:2026.2.92_v9.0.319-90.3.el9_8`; its license matches the baseline.
  Mermaid CLI 12.2.0 resolves DOMPurify 3.4.17. The npm audit still reports the same pre-existing
  High Zod advisory and its Puppeteer dependency paths.
- 2026-11-20: Dependency synchronization, lock verification, formatting, lint, CI policy,
  OpenAPI validation, and the Linux-target type check passed. On macOS, the native type check
  reported 18 Linux-only API diagnostics. The targeted test run passed 496 tests, deselected
  16 engine/runtime tests, and found three macOS failures. The two supply-chain shell tests
  passed with GNU `mv` on the path. The anydoc SBOM test requires the reviewed Linux wheel.
  All 66 LibreOffice unit tests also passed against pypdf 6.21.1, the supported lower bound.
  Mermaid CLI 12.2.0 rendered the fixture with local Chrome and the strict configuration.
  Final-image builds, supply-chain scans, E2E, and hosted document-engine tests
  remain subject to pull-request CI. The issue-write job is eligible on trusted main runs.
- 2026-11-20: Pinned the reverse-attempt image to `firecrawl-anydoc==0.2.5` in PR #339.
  Verified the PyPI wheel, its embedded Cargo SBOM, and the Apache-2.0 election for
  `constant_time_eq`. The SBOM contains `zip` 9.5.1, which fixes GHSA-m665-v7pm-7grj,
  and Grype matched no advisories. On Linux, 1,062 targeted tests, the type check, and a
  corpus parse through the product adapter on the pinned UBI base passed. PR CI qualifies
  the final images and E2E workflows.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-774.
