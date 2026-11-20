---
ticket: T100
linear_id: G1L-619
linear_url: https://linear.app/g1lom/issue/G1L-619/t100-automate-published-image-receipt-adoption-after-a-release
status: In Progress
priority: Medium
project: Markdown to DOCX and PDF Converter
---

# T100 - Automate published image receipt adoption after a release

## Objective

Remove the hand-edited follow-up that adopts the published GHCR receipt digests after each release: the release workflow prepares the adoption branch from verified publication evidence and dispatches CI on it, and a maintainer opens the pull request with one printed command.

Created from the repository analysis accepted by the owner on 2026-10-09 (section: what to change, item 6).

## Acceptance criteria

- After a successful PyPI and GHCR publication, the workflow generates the Compose and quickstart pin changes only from the verified registry receipts; it never infers or pre-pins an unpublished digest.
- It pushes a `chore/adopt-release-<version>` branch, dispatches CI on it, and prints the single `gh pr create` command a maintainer runs; the PR still passes the normal required checks and independent review before squash merge. Opening the PR automatically is a follow-up that needs a GitHub App or token owner decision.
- Failure or partial publication produces no branch and a clear workflow summary.
- Update `docs/releasing.md` and the AGENTS.md release rule accordingly.
- Test the generation logic with unit tests and a dry-run workflow path.

## Dependencies

- None.

## Blocking points

- Repository settings currently forbid Actions from creating pull requests. Fully automatic PR creation remains a follow-up pending an owner decision on a dedicated GitHub App or PAT. The existing `GITHUB_TOKEN` can prepare the branch and dispatch CI, and a maintainer opens the pull request.

## Progress

- 2026-10-09: Created in Linear and mirrored here from the owner-accepted repository analysis.
  Not started.
- 2026-11-20: Added verified receipt adoption for Compose and the quickstart pins, branch CI dispatch, and a maintainer command in the release summary. Added a read-only dry run and tests for exact edits, incomplete evidence, and branch retries.

## Synchronization

Keep status, scope, acceptance criteria, dependencies, and progress aligned with G1L-619.
