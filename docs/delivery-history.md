# Delivery history

**Status:** Non-normative record

This page keeps the delivery narrative that used to live inside the
[product specification](product-specification.md): completed ordering notes, dated owner
decisions and priorities, ticket coordination for finished work, and release history. It explains
how the current contract was reached. It does not define requirements. When this page and the
specification differ, the specification prevails.

The text below is moved verbatim from the specification unless a note says otherwise. Each
heading names the specification section it came from. Current ticket status lives in the
`tickets/Txx-*.md` mirrors and the
[Linear project](https://linear.app/g1lom/project/markdown-to-docx-and-pdf-converter-3724edb949f9).

## Decision provenance

### Frontend runtime baseline review dates (from section 2)

The section 2 "Frontend runtime baseline" row recorded that the exact Next.js, TypeScript, and
Tailwind CSS pins were "reviewed on 2026-09-03; Next.js moved from `16.3.4` to the `16.3.8`
security patch on 2026-10-12 (T133)".

### Reverse-conversion isolation ordering note (from section 2)

The section 2 "Reverse-conversion execution isolation" row ended with: "T70-T73 can proceed
independently."

### Next.js migration staging (from section 3.3.1)

T60–T63 left the legacy FastAPI pages on the production route while building and verifying
the frontend foundation, authentication, conversion, and administration parity. T64 completed
parity and rollback rehearsal while the candidate branch still contained the legacy renderer, then
removed the legacy code and assets.

### Composer native-preview approval (from sections 3.6.5 and 14)

From section 3.6.5: the user approved one narrowly scoped native Office preview boundary on
2026-09-23.

From the section 14 "Composer programme and decision gates" subsection: the user decided on
2026-09-23 that qualified native DOCX/PPTX previews are required in the first Composer delivery.
PDF-first substitution is rejected. The user subsequently approved only the isolated iframe and
route-scoped CSP boundary specified in section 3.6.5 after independent feasibility review.

### Capability decisions D1–D16 (from section 3.7)

On 2026-10-09 the owner recorded the D1–D15 decisions for T96.

For D2, on 2026-10-10 the owner decided how clients find references.

D15 (T108) was amended on 2026-11-20. On 2026-11-20 the owner restated the core product as
Markdown to DOCX, PDF, and editable PPTX, amended D15, and added D16.

### Tracking triage of 2026-11-25 (from sections 3.7, 11, 13, and 14)

On 2026-11-25, after a three-model review of project tracking, the owner made these decisions
(recorded by T161):

- T134 is Done. Release 0.8.0 qualified the staged image set before any irreversible
  mutation; two failed attempts left no tag, GitHub Release, or PyPI upload.
- T74 is cancelled, because T107 removed the Kubernetes reverse backend from main.
- T92 and T93 are cancelled under D16; 0.8.0 had shipped without T93. Section 14 previously
  planned for T93 to move the version from 0.7.3 to 0.8.0.
- T119, T123, T125, T126, and T127 are cancelled because no recorded decision approves them; D13
  and D14 had kept T126 and T127 in the backlog. T115, T116, T117, and T122 stay open because D8
  to D11 approve them.
- Section 11 now allows manual release recovery to publish missing GHCR images from the exact
  retained, qualified, and digest-verified bytes, as the release workflow and `docs/releasing.md`
  already allowed. Until then, the specification limited recovery to evidence.

### Restore compatibility decision (from section 8.2)

The section 8.2 rule that restore accepts recovery sets created at schema revision `20260829_14`
or later was an owner decision of 2026-10-11 (T128).

### Repository ownership decision (from section 13)

The 2026-09-21 user decision keeps Markweave under the personal GitHub account. T48 retains
repository-owned pull-request and scheduled mutation checks with independent review of workflow
and policy changes. These checks remain modifiable in a pull request; contributor-immutable
enforcement is no longer required. No organization, Enterprise subscription, repository transfer,
separately owned policy repository, or external check provider is a prerequisite. Existing mutation
tests, reviewed exclusions, strict failure semantics, and coverage thresholds remain required.

The standing requirements of this paragraph now appear in section 11 of the specification.

## Completed ticket coordination

### CLI command-family ownership (from section 3.4)

T31 owns the root command registry and pre-registers stable, initially unavailable command-family
modules for authentication, conversions/jobs, templates, administration/audit/health, runtime
operations, and recovery operations. T36 exclusively fills the runtime-operations family for
`serve`, `worker`, `doctor`, and `migrate` in `src/markweave/cli/commands/runtime.py`; T37
exclusively fills the recovery-operations family for `backup` and `restore` in
`src/markweave/cli/commands/recovery.py`. Downstream CLI tickets replace only their assigned family
implementation and tests;
they do not edit the root registry or shared help snapshots. T50 owns the final cross-family help
and end-to-end integration snapshots.

### Test sequencing exceptions for T06 and T12 (from section 10)

The project manager approved one sequencing exception for T06: its login, session, and local-account
administration flows receive unit, functional ASGI, and real Argon2id/HTTP integration coverage in
T06, while final-image rootless E2E is durable T20/T21 debt. The architectural reason is that T06
deliberately introduces neither the final UBI image nor the standalone/distributed persistence and
deployment boundaries. T20/T21 must repeat the primary flow and relevant authentication,
authorization, revocation, expiration, cookie, and recovery failures against the hardened image;
this is a sequencing exception, not a waiver of final E2E coverage.

The project manager also approved a T12 sequencing exception: T12 must run provider-neutral contract
tests and real PostgreSQL/RustFS integration tests for the primary successful path and every relevant
failure behavior, but its final-image rootless E2E is durable T20/T21 debt because T12 does not yet
deliver the hardened image. T20/T21 must exercise both profiles against that image, including the
relevant storage success, failure, restart, recovery, and concurrency paths. The pull request must
justify this exception and receive explicit reviewer approval; this is not a waiver of integration
coverage or final E2E coverage.

### 2026-10 repository analysis (from section 13)

On 2026-10-09 the owner accepted the repository analysis that created T96–T127. The owner kept
the experimental reverse conversion and asked for its scope to be frozen (T108) rather than removed.
T96 records the owner's scope decisions D1–D15 in section 3.7. A ticket that depends on T96 may
start once T96 is merged on main; until then the earlier requirements remain authoritative. D12
cancels T124, D11 removes EPUB from T122, and D13 and D14 keep T126 and T127 deferred.
T97, T99, T100, T102, T103, T107, T109 and T110 need no scope decision; T97, T102, T107 and T110
still carry the owner actions or release constraints recorded in their tickets. The
competitor-feature tickets T111–T127 start only after the in-progress Composer iterations T89–T91
are Done; this work-in-progress limit is an ordering rule and does not add blocking dependencies. Only one ticket
edits this specification at a time, so T101 follows T96.

The rule that only one ticket edits the specification at a time remains in section 13 of the
specification.

### Composer programme sequence (from section 13)

The Composer programme approved on 2026-09-22 follows T88 qualification, then T89–T92 as four
cohesive implementation iterations and T93 release/adoption. The earlier priority notes below
record the preceding release programme; they do not supersede this sequence.

### Priorities approved on 2026-09-21 (from section 13)

The next priorities approved on 2026-09-21 are T50 qualification, then T73 reverse-conversion
qualification, T85 history filtering, T86 CI/dependency reliability, and T83 structured PowerPoint
extraction. T48 mutation CI integration is independent work. T74 remains deferred until a concrete
Kubernetes deployment need justifies it. Small documentation and obsolete-code cleanups may
accompany focused, reviewed changes. This ordering does not add blocking dependencies between
otherwise independent tickets or authorize a new public release version.

### Recommended delivery order (from section 13)

Recommended delivery order: T00 and T01 can start in parallel, and T00 may continue alongside only foundation work that does not depend on its unresolved outcomes. T04 still waits for both T00 and T01. Continue with the remaining autonomous foundation (T02–T05), document conversion (T06–T11), storage/queue/ownership (T12–T15), Web product (T16–T17), then industrialization (T18–T23), followed by the trusted-upstream deployment option, its rootless compatibility correction, the public-origin correction, the CI/origin reliability follow-up, the bounded SSH-tunnel evaluation mode, optional-template conversion, and startup user provisioning with required password renewal (T24–T30). For the frontend migration, complete T58 first; T59 and T60 may then proceed independently, followed by T61, the authoritative runtime-metadata prerequisite T65, and the authoritative session-policy-bounds prerequisite T66 before the parallel workflow migrations T62 and T63 and the single verified cutover T64.

T68 follows T64 as the focused correction for host forwarding into the shared rootless Podman
network namespace. It does not change the router's public-host policy or the host's loopback-only
publication boundary.

### Reverse-conversion delivery order (from section 13)

For experimental reverse conversion, T69 fixes the approved evidence and contract. T70 implements
the trusted external isolation broker and its rootless Podman backend, authenticated bounded
protocol, disposable attempt runner, bounded internal renderer adapter, and package builder. T71
binds that runner and its content-free stable-unit termination proof to persistent leases, recovery,
publication, and the backend workflow. T67 follows T64 and establishes the normative
package-manager, bootstrap, workspace, command, and lockfile contract before T72 starts. T72 then
builds the Revert workspace on that finalized pnpm toolchain. T46 and T50 must finish
their baseline security/support policies and cross-surface documentation/acceptance
ownership before T73 begins. T73 may then add only reverse-specific extensions to those established
surfaces. T48 is not a blocking dependency, directly or through T50; its remaining mutation CI
integration remains separate follow-up work. T50 qualifies the existing mutation baseline without
waiting for T48 completion, and remains a blocking prerequisite for T73.
T73 does not reopen their baseline scope or edit an exclusively owned path while another
ticket is active. T73 owns the complete final-image, two-profile, cross-format, reverse-security,
dedicated reverse-documentation, third public reverse-attempt image contract, and release-readiness
acceptance matrix. OCR remains outside this sequence. T74 separately owns optional Kubernetes
support and does not block T70-T73.

### T31–T50 parallel work plan (from section 13)

For T31–T50, begin T31, T39, and T44 in parallel because their owned paths do not overlap. T32
follows T31. T33, T34, and T35 then run in parallel by filling the command-family modules and test
fixtures pre-registered by T31; they never edit the root registry or shared help snapshots. T36 and
T37 may run in parallel after T31 and T39 because they fill separate pre-registered runtime- and
recovery-operations families. T40 follows the CLI and configuration foundations and is
the sole owner of `pyproject.toml`, package extras/metadata, and release-install verification after
T31's initial entry-point change. T41 and T43 follow T44 and run independently. T42 follows T43 so
the worker decomposition consumes finalized ports without concurrent port edits. T45 follows T41;
T46 and T49 follow T40 and run in parallel on dedicated policy files and namespace-cleanliness
checks without editing distribution metadata or release-install verification. T47 follows T39 and
owns only its dedicated changelog, upgrade guide, and changelog-check files. T48 waits for the
refactored mutation targets. T38 integrates the finished CLI into container assets and executable
deployment/recovery tests without editing shared documentation navigation. T54 follows T38, T40,
and T22 to publish and pin the public Compose and quickstart migration, before T50 performs final
cross-surface acceptance and exclusively owns README, `docs/index.md`, and cross-guide navigation
updates. Each ticket lists its exclusive files or components; a worker must stop and resynchronize
the ticket before touching any path owned by another active ticket.

The last sentence, the general file-ownership rule, now appears in section 9 of the specification.

## Release history

### PyPI first-publication bootstrap (from section 11)

Before the first public release, configure a PyPI pending Trusted Publisher for project `markweave`, owner `Guillaume-Lombardo`, repository `simple-md-to-docx-converter`, workflow `release.yml`, and environment `pypi`. Immediately before every upload, recheck that the exact `markweave` version is unpublished. A pending publisher does not reserve the distribution name. The first successful OIDC upload creates the PyPI project and converts the pending publisher into a normal Trusted Publisher; verify both the project and publisher state after that upload. The public license is Apache-2.0.

Section 11 of the specification keeps the publisher identity, the per-upload recheck, and the
license.

### Release 0.6.0 to 0.6.3 (from section 11)

The `0.6.0` cutover was the sole skipped-container exception: its exact GitHub tag/Release and PyPI artifact were published from the reviewed source, but its paired container job failed before staging or registry authentication and both `0.6.0` GHCR role tags remained absent. The protected `0.6.0` to `0.6.1` transition verified that state before running an ordinary new paired release; neither manual recovery nor any workflow may rebuild or publish `0.6.0`. After successful `0.6.1` publication, Compose and both quickstarts pinned the exact verified backend and frontend registry digests from source `78cb86d450e940a3190591de62ee0ebade216d8b`. After successful `0.6.3` publication, they pin the exact verified backend digest `sha256:6560d86e4ca33327a5f454530c8b6a2fadb20b55af6373aea01378b00920bb4e` and frontend digest `sha256:bb60b8b72259d738c4eb93c29cf54aef9a8cf2f875e5851ebdc063ded5c99fa5` from source `5e789c11600d429997c037b4d24eea399821a2ed`.

Section 11 of the specification keeps the rule that no workflow may rebuild or publish `0.6.0`.

### Release 0.7.1 (from section 11)

The published `0.7.1` pair from source `5dd3328a17d12279d1c7c11a8c96b68cb062ecb3`
adopts backend `sha256:10c84da1e783e86f56163c6bb639008436d6878462ac63e62af8a28129599a93`
and frontend `sha256:dad65e90b56923fb38df3fc985b51fb20ef40422ff8ccd2aae2ece1b17515082`
from the verified receipts of successful release run `35537766223`.

### Releases 0.7.2 and 0.7.3 (from section 13)

On 2026-09-22, the user separately authorized T87: validate the final documentation, then publish
patch 0.7.2 through the existing protected workflow, verify the complete public image set, adopt
its exact registry receipts, and clean up the merged work branches. The 0.7.2 Python artifacts and
tag were published, but container qualification failed before image publication or artifact
retention. The user subsequently authorized correcting the T73 harness and publishing 0.7.3 under
a narrowly verified 0.7.2 failed-container continuation, preserving immutable 0.7.2 history and the
existing 0.7.1 deployment pins until new public receipts exist. T87 completes T73's public
reverse-attempt image criterion after technical qualification; it does not depend on that
publication criterion being completed beforehand. T74 remains deferred.

### T83 follow-up scope and release 0.7.0 (from section 14)

T82 delivers editable PowerPoint generation and original-source packages in 0.7.0.
T83 retains the unfinished slide-oriented Markdown/Marp extraction options from
edited PPTX files under the existing reverse isolation contract. It is not part of
the 0.7.0 forward-workflow completion claim.

## Complete delivery ticket table (from section 13)

This is the section 13 table as it stood before T101. Ticket outcomes and dependencies are the
historical delivery plan; the ticket mirrors hold the reviewed scope and acceptance criteria.

| Ticket | Outcome | Depends on |
|---|---|---|
| T00 | Validate UBI 9/Python 3.14, Pandoc, Chromium/Mermaid, LibreOffice, sandboxing, fonts, resource budgets, and rootless runtime through spikes | — |
| T01 | Initialize the English repository, `uv` project, architecture, commands, contribution rules, and local developer workflow | — |
| T02 | Protect `main`, configure required gates, independent review, merge queue or serialized merge, and squash policy | T01 |
| T03 | Implement selective GitHub Actions workflows, `merge_group`, caching, permissions, timeouts, and required gate | T01, T02 |
| T04 | Build the corpus, golden infrastructure, fixtures, marker registration, and deterministic comparison tools | T00, T01 |
| T05 | Configure Ruff, `ty`, Pytest, pytest-cov, pytest-mock restriction, 90% thresholds, and changed-line coverage | T01, T03 |
| T06 | Build FastAPI foundation, configuration, English errors, local accounts, sessions, authorization abstraction, and health endpoints | T01, T05 |
| T07 | Convert approved Markdown to DOCX with fixed Pandoc arguments and reference documents | T04, T06 |
| T08 | Secure ZIP handling, safe extraction, image normalization, hostile SVG handling, and security tests | T04, T07 |
| T09 | Render Mermaid through local Chromium under arbitrary UID, bounded resources, and rootless constraints | T00, T08 |
| T10 | Inventory fonts and licenses; validate OOXML, templates, required styles, substitutions, and canonical conversion | T00, T07 |
| T11 | Produce PDF with isolated LibreOffice profiles, traceability manifest, timeout/cancellation, and golden tests | T09, T10 |
| T12 | Implement repository/object-store abstractions, both profiles, Alembic migrations, atomic files, and contract tests | T05, T06 |
| T13 | Implement persistent queue, job API, state machine, idempotency, embedded/external workers, leases, heartbeat, recovery, and cleanup | T11, T12 |
| T14 | Add immutable ownership, global visibility, search, preferences, fallback template, and cross-profile authorization tests | T06, T12 |
| T15 | Implement versioned template API, downloads, ETag/If-Match, atomic replacement, copy-forward restore, audit, and profile parity | T10, T14 |
| T16 | Build asynchronous conversion UI, template search, progressive polling, cancellation, expiration, and accessible downloads/errors | T13, T14, T15 |
| T17 | Build owner/admin template UI and administrator local-account management with multi-user browser tests | T15, T16 |
| T18 | Add quotas, queue capacity, resource budgets, retention, periodic cleanup, cancellation, and short load tests | T00, T12, T13 |
| T19 | Add structured logs, correlation, metrics, queue observability, audit, version traceability, and cheap readiness | T15, T18 |
| T20 | Build hardened reproducible final image with API, embedded-worker, and external-worker modes, SBOM, scans, and smoke test | T11, T12, T13, T18 |
| T21 | Run rootless E2E for both profiles with three identities, real conversion, restart recovery, concurrency, and failure artifacts | T17, T20 |
| T22 | Finalize selective CI/CD, scheduled full suite, targeted mutation testing, grouped dependency updates, release image, SBOM, provenance, and trusted publication of the verified `markweave` sdist and wheel to PyPI | T03, T21 |
| T23 | Complete English user, template, administrator, API, operations, storage, queue, agent, recovery, and deployment documentation | T22 |
| T24 | Support an explicit trusted-upstream malware-scanning boundary and a ClamAV-free Podman quickstart while preserving fail-closed ClamAV defaults | T23 |
| T25 | Support a CNI-free `slirp4netns` Podman quickstart for trusted-upstream antivirus deployments and publish patch release `0.3.3` | T24 |
| T26 | Preserve strict login-origin validation on custom quickstart ports and same-host reverse proxies, and publish patch release `0.3.4` | T25 |
| T27 | Cache checksum-locked LibreOffice CI artifacts and verify effective quickstart login origins across Compose providers | T22, T26 |
| T28 | Add an explicit loopback-only insecure quickstart for temporary SSH-tunnel testing, fix native same-origin browser login, and publish patch release `0.3.5` | T24, T26, T27 |
| T29 | Allow conversion without a template by using Pandoc's native default reference document while preserving optional immutable-template selection and traceability | T07, T10, T13, T15, T16, T21 |
| T30 | Provision users from a startup CSV, replace existing passwords, require restricted-session password renewal, and publish minor release `0.4.0` | T06, T12, T17, T21 |
| T31 | Build the installed `markweave` CLI foundation, stable output/error contract, and clean-package entry point | T01, T06, T22 |
| T32 | Add secure HTTP login/logout/session/password-renewal commands and owner-only XDG connection profiles without API tokens | T06, T30, T31 |
| T33 | Add HTTP-only conversion submission and complete user-owned job lifecycle commands | T13, T29, T32 |
| T34 | Add HTTP-only template, version, preference, and fallback administration commands | T15, T32 |
| T35 | Add HTTP-only user administration, audit, health, readiness, and metrics commands | T17, T19, T30, T32 |
| T36 | Add supported `serve`, `worker`, `doctor`, and `migrate` operational commands | T12, T20, T31, T39 |
| T37 | Add guarded standalone and distributed `backup` and `restore` operational commands | T12, T18, T20, T31, T39 |
| T38 | Use the supported `markweave` commands as every source-built final-container, deployment/recovery, smoke, and E2E entry point | T20, T21, T33, T34, T35, T36, T37, T40 |
| T39 | Make `MARKWEAVE_*` canonical and provide fail-closed `MD_CONVERTER_*` compatibility through 0.7.x | T06, T20, T26 |
| T40 | Clarify the supported Python API, split optional backend extras, and complete PyPI metadata and installation verification | T22, T31, T39 |
| T41 | Decompose the FastAPI application into routers, schemas, dependencies, error handling, lifecycle, and a small composition root | T06, T44 |
| T42 | Decompose worker claim, heartbeat, execution, publication, cancellation, recovery, and cleanup orchestration against the finalized persistence ports | T13, T21, T43 |
| T43 | Decompose job and template persistence by responsibility while preserving cross-profile contracts and transactional invariants | T12, T15, T44 |
| T44 | Eliminate unclosed database/component resources and enforce targeted `ResourceWarning` regressions | T06, T12 |
| T45 | Commit and validate a deterministic OpenAPI artifact and block accidental incompatible HTTP changes | T06, T41 |
| T46 | Add security reporting, supported-version, disclosure, and operational-support policies | T22, T23, T40 |
| T47 | Add a user-facing changelog and deterministic package/container/database upgrade and rollback guidance | T22, T23, T39 |
| T48 | Expand bounded mutation testing across authentication, input security, queue, worker, retention, and storage invariants | T05, T22, T41, T42, T43 |
| T49 | Remove residual retired-package artifacts and enforce clean `markweave` namespace and release outputs | T22, T40 |
| T50 | Run the complete package, CLI, container, configuration, contract, documentation, and maintainability acceptance matrix | T38, T41, T42, T43, T44, T45, T46, T47, T49 |
| T54 | Publish the post-T38 CLI-entrypoint release and atomically pin public Compose and quickstarts to its immutable image | T22, T38, T40 |
| T55 | Publish LibreOffice descendant PID probes atomically in the real-process cancellation test harness | T21 |
| T56 | Allow safe HTTP(S) hyperlinks without remote resource loading and verify the workflow against the final image | T07, T08, T21 |
| T57 | Preserve the uploaded filename stem for DOCX, PDF, and combined conversion downloads | T16, T21 |
| T58 | Define the Next.js frontend migration architecture, same-origin API boundary, staged cutover, runtime topology, and rollback contract | T20, T21, T45 |
| T59 | Persist and audit an administrator-controlled idle-session policy enforced by FastAPI across both storage profiles | T06, T12, T19, T45, T58 |
| T60 | Build the `web/` Next.js, TypeScript, and Tailwind CSS foundation, typed API transport, frontend quality gates, and rootless smoke test | T45, T58 |
| T61 | Migrate login, logout, password renewal, protected navigation, and session-expiry behavior to Next.js | T30, T59, T60 |
| T62 | Migrate the asynchronous conversion workflow to Next.js with behavioral, accessibility, and failure parity | T16, T57, T61, T65 |
| T63 | Migrate template, user, and idle-session-policy administration to Next.js | T17, T59, T61, T65, T66 |
| T64 | Cut over browser routing, remove the legacy frontend, harden and publish the frontend runtime, and complete two-profile rootless E2E acceptance | T20, T21, T22, T62, T63 |
| T65 | Expose authenticated domain-specific conversion options, template context, and the administrator absolute-session ceiling for authoritative frontend runtime metadata | T45, T57, T59, T61 |
| T66 | Expose authoritative role-specific idle-session policy bounds, defaults, and minute granularity for the administration frontend | T59, T65 |
| T68 | Restore host routing for the CNI-free rootless Podman trusted-upstream and insecure Next.js quickstarts | T64 |
| T67 | Migrate root browser-test and Next.js tooling to one deterministic pnpm workspace while preserving the isolated npm Mermaid graph, release evidence, and rollback | T64 |
| T69 | Validate and specify the pinned local anydoc engine, supported formats, asset-aware serialization, PDF limitations, supply chain, and resource contract | T04, T20, T45, T64 |
| T70 | Implement the external rootless Podman isolation broker and authenticated bounded protocol, disposable anydoc attempt runner, bounded internal renderer adapter, and deterministic asset-aware Markdown package builder | T08, T18, T20, T69 |
| T71 | Add authenticated persistent reverse-conversion jobs, API, workers, observability, and both storage profiles | T13, T19, T45, T70 |
| T72 | Build the experimental Next.js Revert workspace with accessible stamped navigation and complete asynchronous job behavior | T60, T61, T64, T67, T71 |
| T73 | Harden, document, and verify reverse conversion against exact final images and both storage profiles | T21, T22, T23, T46, T50, T67, T70, T71, T72 |
| T74 | Design and implement the optional Kubernetes reverse-isolation backend and node attester without weakening the T70 proof contract | T70, T71 |
| T75 | Publish patch release 0.6.2 and adopt its verified image pair (completed) | T22, T69, T70, T71, T72 |
| T76 | Rename workflow navigation and publish patch 0.6.3 with verified image-pair adoption | T22, T71, T72, T75 |
| T77 | Make release subprocess termination and reaping reliable | T22 |
| T78 | Make node asset permission tests independent of checkout modes | T05, T20 |
| T79 | Decompose large reverse-conversion modules without changing contracts | T70, T71 |
| T80 | Clean maintenance assets and provide automatic local distributed-test services | T22, T23, T67, T76 |
| T81 | Shorten workflow tab labels to `2docx`, `2md`, and `templates` | T76 |
| T82 | Add editable PowerPoint generation, typed templates, portable sources and slide-oriented reverse conversion | T81, T07, T08, T09, T10, T12, T13, T15, T16, T17, T69, T70, T71, T72 |
| T84 | Continue responsibility-based decomposition of application Python modules above 1,000 lines, preserving imports, transaction/proof boundaries and the single private anydoc adapter | T79 |
| T85 | Filter owner-scoped conversion history by output family and expiration before pagination, avoiding browser history scans | T12, T13, T45, T62, T82 |
| T86 | Diagnose dependency CI failures and make immutable image acquisition resilient to transient transport failures | T22, T27 |
| T87 | Validate final documentation, publish patch 0.7.3 after failed 0.7.2 image qualification with the matched three-image set, and adopt verified public receipts | T22, T83 |
| T88 | Specify Composer and qualify real Office editing and private previews before production code | T04, T12, T13, T20, T21, T45, T64, T82, T83, T87 |
| T89 | Add secure authorized OpenAI-compatible connections, browser setup, and durable drafts, conversations, revisions, and artifacts in both profiles | T88 |
| T90 | Deliver Convert/Composer navigation, chat, proposals, exact-revision previews, history, diffs, and restore | T89 |
| T91 | Add permissioned structured author knowledge and typed repeating document templates | T90 |
| T92 | Deliver qualified structured DOCX/PPTX editing tools and a cited, permissioned document library (remaining scope frozen by D16) | T91 |
| T93 | Complete two-profile/final-image Composer qualification, publish minor 0.8.0, adopt exact published receipts, and deploy the matched public set (Composer qualification frozen by D16; 0.8.0 ships without it) | T92 |
| T96 | Record the owner scope decisions D1-D15 that the 2026-10-09 findings require before implementation | — |
| T97 | Mark Podman-dependent tests and repair the default local test command | — |
| T98 | Make the local Python test suite fast enough for iteration without weakening coverage gates | T97 |
| T99 | Consolidate Compose variants with profiles without changing deployed behavior | — |
| T100 | Automate published image receipt adoption after a release from verified evidence | — |
| T101 | Separate the normative specification from delivery history | T96 |
| T102 | Rename the GitHub repository to markweave | — |
| T103 | Document and test math rendering | — |
| T104 | Accept Markdown with local images without a hand-built ZIP | T96 |
| T105 | Allow a sanitized inline HTML subset | T96 |
| T106 | Add local serverless CLI conversion | T96 |
| T107 | Remove the dormant Kubernetes isolation backend from main, recoverable from an archive tag | — |
| T108 | Freeze the experimental reverse conversion scope | T96 |
| T109 | Relocate completed spikes and archive historical evidence | — |
| T110 | Remove legacy `MD_CONVERTER_*` configuration aliases in 0.8.0 and report replacements at startup | — |
| T111 | Add table of contents, section numbering and page breaks | T96 |
| T112 | Add cross-references for figures, tables and equations | T96, T111 |
| T113 | Add citations and bibliography | T96 |
| T114 | Add scoped revocable API tokens | T96 |
| T115 | Add OIDC single sign-on with group-to-role mapping | T96 |
| T116 | Add signed job-completion webhooks | T96, T114 |
| T117 | Add an MCP server for AI agents | T96, T114 |
| T118 | Add PDF/A and tagged accessible PDF output | T96 |
| T119 | Add a live preview to the conversion workspace | T90 |
| T120 | Add batch conversion and a CLI watch mode | T106 |
| T121 | Provide a GitHub Action and a pre-commit hook | T106 |
| T122 | Add self-contained HTML and ODT outputs (EPUB deferred by D11) | T96 |
| T123 | Add deterministic data-driven DOCX template filling | T91 |
| T124 | Cancelled by D12: administrator-approved Pandoc Lua filter catalogue | T96, T111 |
| T125 | Add VS Code and Obsidian integrations | T104, T114 |
| T126 | Internationalize the browser interface (deferred by D13) | T96 |
| T127 | Publish Linux/ARM64 images (deferred by D14) | T96 |
| T128 | Restore recovery sets created by an older schema | — |
| T155 | Freeze the Composer feature scope (D16) | T108 |
