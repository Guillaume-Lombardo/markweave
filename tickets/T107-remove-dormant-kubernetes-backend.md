---
ticket: T107
linear_id: G1L-627
linear_url: https://linear.app/g1lom/issue/G1L-627/t107-remove-the-dormant-kubernetes-isolation-backend-from-main
status: In Progress
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T107 - Remove the dormant Kubernetes isolation backend from main

## Objective

Remove the roughly 6,500 lines of optional Kubernetes reverse-isolation code that serve the deferred T74 backlog ticket, keeping it recoverable from an archive tag.

Created from the repository analysis accepted by the owner on 2026-10-09 (section: what to remove or freeze).

## Acceptance criteria

- Tag the last commit containing the code as `archive/t74-kubernetes-backend` and reference the tag from T74.
- Remove `src/markweave/broker/kubernetes*`, `src/markweave/kubernetes_attester_process.py`, the CRI protobuf files, the `markweave-kubernetes-attester` entry point, the `kubernetes` optional extra, `containers/kubernetes-attester`, `deploy/k3s`, `deploy/reverse-kubernetes.yaml.example`, the Kubernetes E2E scripts, their tests, CI steps and `docs/kubernetes-reverse-isolation.md`.
- The rootless Podman broker backend, both transports, inventory, reconciliation and termination proof stay unchanged; reverse-conversion tests and both final-image E2E profiles pass.
- Record the removal of the `kubernetes` extra and entry point in CHANGELOG and the upgrade guide.
- Update specification sections 2 and 14 to say T74 would restore the backend from the archive tag.

## Dependencies

- None.
- Related: T74 - Design and implement the Kubernetes reverse-isolation backend

## Blocking points

- The owner confirmed on 2026-10-09 that T74 stays deferred.
- Removing a published optional extra and console script is a packaging compatibility change; it must ship in a release with an upgrade note; target the 0.8.0 minor release, which ships without waiting for the frozen T93 Composer qualification (D16).
- If T96 is still open, T96 owns the specification wording for sections 2 and 14; only one ticket edits the specification at a time.

## Progress

- 2026-11-20: The owner approved the removal for the 0.8.0 release. The annotated archive tag
  `archive/t74-kubernetes-backend` points to main commit `305734be15652850e28bc5711263395c66e7dc8b`.
  Removed 16,366 lines (7,114 source, 7,324 tests, 1,928 other) relative to the T153 base.
  Compared local broker and reverse tests against T153 on macOS. All shared outcomes matched,
  and the added configuration rejection test passed. Verified the wheel and source archive
  contents. The Linux release integration and both final-image E2E profiles remain CI checks.
- 2026-10-09: Created in Linear and mirrored here from the owner-accepted repository analysis.
  Not started.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-627.
