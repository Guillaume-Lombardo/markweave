---
ticket: T132
linear_id: G1L-685
linear_url: https://linear.app/g1lom/issue/G1L-685/t132-restore-distributed-recovery-sets-with-jobs-on-superseded
status: Backlog
priority: High
project: Markdown to DOCX and PDF Converter
---

# T132 - Restore distributed recovery sets with jobs on superseded template versions

## Objective

Make distributed (PostgreSQL/S3) restore accept valid recovery sets in which a retained conversion
job references a template version that a newer published version has since superseded.

Found on 2026-10-11 during T128 (PR #290) and confirmed by independent review round 3. After a
succeeded job froze template version 1 and version 2 was then published, distributed restore
refuses both a `20260923_24` recovery set and a current-head production backup, including on
unmodified `origin/main`. The PostgreSQL insert-time integrity trigger accepts a job only when its
template version is the template's current version, so the frozen historical pair is rejected even
though both versions exist. Admission enforces "current version" at submission time, but recovery
must accept historical jobs.

## Acceptance criteria

- Distributed restore accepts recovery sets whose retained jobs reference superseded but existing
  template versions, while still refusing genuinely inconsistent references (missing version,
  version of another template, cross-owner references).
- Admission behavior for new jobs is unchanged.
- The fix keeps database integrity enforcement in place (no blanket trigger disabling); document
  how restore and admission rules differ.
- Real PostgreSQL/S3 integration and final-image recovery coverage restore a set containing a job
  on a superseded template version, at the current head and at an older supported revision;
  standalone parity is verified.
- Update the recovery documentation, which T128 updated to disclose this limitation.

## Dependencies

- T128 - Restore recovery sets created by an older schema (shares the distributed restore code
  path). Done.

## Blocking points

- None known.

## Progress

- 2026-10-11: Created in Linear.
- 2026-11-25: Mirrored here by T161; it was missing from the repository. Status unchanged
  (Backlog).

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-685.
