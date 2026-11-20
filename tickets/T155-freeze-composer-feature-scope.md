---
ticket: T155
linear_id: G1L-776
linear_url: https://linear.app/g1lom/issue/G1L-776/t155-freeze-the-composer-feature-scope
status: In Progress
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T155 - Freeze the Composer feature scope

## Objective

Stop adding Composer features until the owner revisits the workspace, as T108 does for the
experimental 2md reverse conversion. The core product is Markdown to DOCX, PDF, and editable
PPTX; Composer stays an optional workspace.

Created from the owner decision of 2026-11-20: for Composer and 2md, only bug fixes, security
fixes, dependency updates, regression fixes, and removals are accepted. Any new capability needs a
new ticket with an explicit owner decision. No code is removed, and all Composer tests stay in CI.

## Acceptance criteria

- The product specification (section 3.7, decision D16) and `AGENTS.md` state the freeze.
- Open Composer feature tickets (T92 remaining scope, T93) are moved out of In Progress with a
  frozen note; their delivered parts stay documented.
- Composer remains optional: model-assisted operations still require a configured, enabled, and
  authorized LLM connection, and retained drafts, revisions, and exports stay accessible without one.

## Dependencies

- Related: T108 - Freeze the experimental reverse conversion scope.

## Blocking points

- The owner decides when the freeze ends; that decision reopens scope through a new ticket.

## Progress

- 2026-11-20: Created from the owner decision and mirrored here. Started on
  `docs/T155-freeze-composer-and-2md` together with T108. Specification section 3.7 now records
  the shared freeze rule, amends D15, and adds D16; sections 3.5, 3.6, 13, and 14 point at them.
  `AGENTS.md` gains a scope-freeze rule. T92 and T93 move to Backlog with a frozen note; T94 was delivered by PR #271 on 2026-09-26 and its
  mirror is synchronized to Done;
  their delivered progress is unchanged. README and `docs/index.md` record both freezes. The
  existing Composer guards are unchanged: the workspace stays disabled until an administrator
  configures an LLM connection. Documentation only; no code or test is removed.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-776.
