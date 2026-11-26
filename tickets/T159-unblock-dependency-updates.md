---
ticket: T159
linear_id: G1L-850
linear_url: https://linear.app/g1lom/issue/G1L-850/t159-unblock-dependency-updates
status: In Progress
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T159 - Unblock dependency updates

## Objective

Restore compatibility with ty 0.0.107 for the admission-window E2E fixture and restore Dependabot updates for the root pnpm workspace.

## Acceptance criteria

- Ruff formatting and lint, the locked ty check, and ty 0.0.107 all pass.
- Both workspace manifests accept the exact CI and image runtime, Node.js 24.19.0, and the [Dependabot updater's Node.js 24.22.3](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/actions/runs/45112468100). The range excludes Node.js 25 and later.
- Frozen installation passes on both Node.js versions. The web checks, tests, and build pass on the pinned 24.19.0 runtime.
- The canonical fast Pytest suite passes, and the hosted pull-request CI gate is green.

## Dependencies

- T03 (selective CI and required gate) and T67 (pnpm workspace and release evidence).
- [Dependabot Python PR #355](https://github.com/Guillaume-Lombardo/simple-md-to-docx-converter/pull/355) identifies the ty regression. Its dependency changes are outside T159.

## Progress

- Started implementation from `origin/main` on `fix/t159-unblock-dependency-updates`.
- Reproduced the `invalid-assignment` diagnostic with ty 0.0.107. Renaming the receiver to `self` passes both ty 0.0.105 and 0.0.107. The targeted admission and mTLS tests pass (11 tests).
- The manifest range represents compatible Node.js versions. CI and release images still use the exact reviewed runtime. Revisit the runtime upgrade when both digest-pinned UBI 9 images ship Node.js 24.22.3. The latest Linux/AMD64 builder and minimal runtime layers were verified by digest and both contain Node.js 24.22.1.
- Verified both engine declarations with semver and a frozen pnpm install under Node.js 24.19.0 and 24.22.3.
- On Node.js 24.19.0 the workspace check, browser-module tests, frontend checks, 898 Vitest tests, Next.js build, and five production tests passed. The Vitest rerun used two workers after the initial local run failed three existing tests.
- The canonical fast Pytest suite passed on Linux with 6,559 tests and 94.50% coverage. Its engine and Podman markers deselected 136 tests.
- Independent review approved the implementation in one round.
- 2026-11-26: #359 merged as 780e235 and the main CI is green. This issue stays In Progress until the next weekly Dependabot npm update job for `/` succeeds (expected Monday 2026-11-30); that job is the acceptance evidence. Follow-up: move the runtime Node to 24.22.x once UBI ships it.
