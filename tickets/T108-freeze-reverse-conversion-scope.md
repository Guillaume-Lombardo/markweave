---
ticket: T108
linear_id: G1L-632
linear_url: https://linear.app/g1lom/issue/G1L-632/t108-freeze-the-experimental-reverse-conversion-scope
status: Done
priority: Low
project: Markdown to DOCX and PDF Converter
---

# T108 - Freeze the experimental reverse conversion scope

## Objective

Keep the experimental 2md reverse conversion, but freeze its feature scope until the owner revisits it.

Created from the repository analysis accepted by the owner on 2026-10-09 (section: what to remove or freeze (owner kept 2md)).

## Acceptance criteria

- Record in README/`docs/index.md` the D15 freeze stated in specification section 3.7 (amended by the owner on 2026-11-20): 2md is kept, experimental, requires the external broker, and is feature-frozen: only bug fixes, security fixes, dependency updates, regression fixes, and removals are accepted; a new capability needs a new ticket with an explicit owner decision.
- List the reverse-conversion tickets and ideas that are paused (including OCR and the T74 Kubernetes backend).
- No code is removed; all reverse-conversion tests remain in CI.

## Dependencies

- T96 - Approve the 2026-10 scope changes in the product specification

## Blocking points

- Owner decides when the freeze ends; that decision reopens scope through a new ticket.

## Progress

- 2026-10-09: Created in Linear and mirrored here from the owner-accepted repository analysis.
  Not started.
- 2026-11-20: Started on `docs/T155-freeze-composer-and-2md` together with T155 after the owner
  decision of 2026-11-20. That decision amends D15 in specification section 3.7: the shared freeze
  rule accepts bug fixes, security fixes, dependency updates, regression fixes, and removals only;
  any new capability needs a new ticket with an explicit owner decision. 2md stays experimental
  and requires the external broker. README and `docs/index.md` record the freeze and list the
  paused tickets and ideas: OCR for scanned or image-only inputs, Firecrawl's hosted Parse
  fallback, formats beyond the T69 matrix, PDF images and layout, original-source recovery and a
  full visual round trip for edited PPTX, and the T74 Kubernetes backend, which T107 archives
  under the tag `archive/t74-kubernetes-backend`. Documentation only; no code or test is removed.
- 2026-11-21: Merged in #341; CI passed on `main` at `199f92f`. Closed.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-632.
