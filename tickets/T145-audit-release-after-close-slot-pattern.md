---
ticket: T145
linear_id: G1L-698
linear_url: https://linear.app/g1lom/issue/G1L-698/t145-audit-the-release-after-close-slot-pattern-in-the-metrics-server
status: Backlog
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T145 - Audit the release-after-close slot pattern in the metrics server

## Problem

T141 (G1L-694, PR #304) fixed a race in the broker transports. A server released its bounded admission slot only after the connection close that completes the client's exchange. A client that reconnected at once could then be refused at the admission limit.

During T141, `_BoundedMetricsHttpServer` in `src/markweave/observability.py` was seen using the
same release-after-close ordering. It was left out of scope. The Kubernetes node attester transport
seen at the same time was removed from main by T107; it is out of scope.

## Scope

- Confirm whether a client can observe completion (EOF, close_notify or the end of the response) before the slot is released. Then decide whether a refused or reset reconnection is reachable at the configured limits.
- Where the race is reachable, release the slot before the completion the client observes, and keep the bounded-admission semantics.
- If fixed, add a deterministic regression test: delay the release, then reconnect immediately at the limit. The test must fail without the fix.
- Add integration or final-image E2E coverage as AGENTS.md requires for the affected workflow, or record why none is needed.

## Acceptance criteria

- The metrics server is either fixed with a failing-without-fix regression test, or documented with evidence that the race is unreachable.
- The canonical checks pass.

## Dependencies

- T141 (G1L-694), merged as `cd98c07`. Reuse its slot-release test approach.

## Progress

- 2026-10-13: Created from the out-of-scope observation recorded during T141.
- 2026-11-25: Scope narrowed by owner decision (T161): the Kubernetes attester transport was
  removed from main by T107 (#340), so only the metrics server remains.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-698.
