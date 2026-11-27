# Release process

`project.version` in `pyproject.toml` is the authoritative PEP 440 version, and every release tag
is derived as `v<project.version>`. The source
and `markweave` distribution are Apache-2.0 licensed, the public import is `markweave`, and the
container repository is `ghcr.io/guillaume-lombardo/md-converter`.

A protected pull-request merge to `main` is the sole human release gate. When that merge changes
`project.version`, the automatic workflow compares the exact before and head commits from the
trusted push. A `pyproject.toml` edit that leaves the version and the positive integer
`tool.markweave.release.attempt` unchanged is a successful no-op. After an infrastructure failure
leaves a release run impossible to rerun and creates no tag, GitHub Release, PyPI version, or GHCR
version tag, a protected recovery pull request may increment `attempt` by exactly one to retry the
same final version. The next version transition must reset it to `1`. Decreases, skipped attempt
numbers, and stale attempts on a new version fail closed. Pull requests, forks, tags, and GitHub
Release events cannot start publication. Manual dispatch cannot publish Python artifacts; it is
reserved for the container-only recovery described below.

The read-only CI workflow verifies the public release identity through fixed HTTPS endpoints on
main pushes, Release events, scheduled and manual runs, and candidates that change
`project.version`, `tool.markweave.release.attempt`, or the public Compose or quickstart image pins.
Other pull requests and merge-group candidates check local release metadata and image pins
without contacting PyPI, GitHub Releases, or GHCR for alignment. A candidate that carries an
unchanged pending release must adopt the published images before other changes can proceed.
For pull requests, CI compares the synthetic merge commit with its first parent. The backend and
frontend defaults in both quickstarts must match the Compose image pair. Keep each quickstart
default on a standalone `readonly` declaration with a contiguous image reference so receipt
adoption can update it.
In the normal state, `project.version`, the latest PyPI version, the Compose image tag, the
published GitHub tag and Release receipt, and the anonymous GHCR manifest digest must all agree;
the Compose reference must include that immutable digest. The only exception is an exact version
transition on a pull request, merge-group candidate, or trusted `main` push: the base project,
PyPI, and Compose versions must still agree, the new project version must be higher, and all public
evidence for the base version must remain valid. Scheduled, Release, and manual runs never receive
this exception. A later revision at the unchanged new version also fails until the published image
has been adopted, except the protected recovery revision that increments `attempt` by exactly one
over its base at that same unpublished version.

The retired exceptions for `0.6.0`, `0.7.2`, and `0.7.4` remain in the archived
[release history](archive/evidence/release-migration-history.md), with the original source SHAs,
run IDs, and publication receipts.

## GitHub and PyPI trust configuration

Keep the GitHub Actions environment `pypi` without required reviewers, wait timers, deployment
restrictions, or environment secrets. It is only the OIDC Trusted Publisher identity boundary.
Configure the PyPI Trusted Publisher with these exact values:

- PyPI project name: `markweave`
- GitHub owner: `Guillaume-Lombardo`
- GitHub repository: `markweave`
- Workflow: `release.yml`
- Environment: `pypi`

No PyPI token belongs in GitHub. The owner adds the publisher above as a second publisher and
removes the old one only after the first successful release from the renamed repository. Verify
the new publisher before merging a version transition. The GHCR package names are stable. Verify
anonymous pull access after every release and grant package access only to the publishing repository.

## Prepare a version release

1. Change only the intended release version in `project.version` and the matching application
   version source. Use canonical final public PEP 440 syntax. Pre-releases, development releases,
   local versions, epochs, invalid spellings, version downgrades, and mismatched application
   versions and transitions with equal PEP 440 precedence fail closed. Reset
   `tool.markweave.release.attempt` to `1`.
2. Open a pull request and require the complete `CI / gate`, independent review, and protected
   merge to `main`. Release versions are derived dynamically and are not hardcoded in the
   workflows.
3. After merge, the workflow verifies the exact `github.event.before` and `github.sha` pair. It
   stops if `v<version>` already exists, a GitHub Release already uses that tag, or PyPI already has
   that exact `markweave` version.
4. The workflow builds the wheel and sdist once from the reviewed main SHA, validates bounded
   metadata and integrity, and installs the exact wheel in a clean Python 3.14 environment. Only
   those verified files are transferred to the `pypi` environment job.
5. In parallel, the read-only reusable `container-qualify.yml` workflow qualifies the container
   images before any irreversible external mutation. Its `stage` job checks out the same SHA and
   builds the backend, frontend, and reverse-attempt images once, with the reviewed commit
   timestamp, then exports each one as an OCI archive bound to its image ID and transfers it within
   the run. Parallel jobs load those archives only after the archive, loaded, and tagged image IDs
   equal the build output: `smoke` runs the final-image, API, distributed, recovery, and frontend
   smokes; `supply-chain` generates the SBOMs and runs the Critical-vulnerability gate, then retains
   the complete backend/frontend/reverse-attempt staging artifact `container-stage-v<version>`;
   and four `e2e` jobs run both shards of both storage profiles. No qualification job holds a write
   permission or a registry credential.
6. Only after both the Python artifacts and the container qualification succeed does a minimal
   `contents: write` job atomically create the tag ref at the exact reviewed SHA before publishing
   the matching GitHub Release. A container build, smoke, scan, or E2E failure therefore leaves no
   tag, GitHub Release, or PyPI version; rerun the failed jobs, or use the attempt mechanism above
   when the run cannot be rerun. A failed-job rerun accepts a partially created tag or Release only
   after verifying its exact SHA, tag, target, draft, and prerelease state. The PyPI job then
   rechecks that the version is still unpublished and uploads the verified files with PEP 740
   attestations through OIDC.
7. The reusable container publication workflow verifies the Release identity, downloads the
   qualified staging artifact from the same run, and never rebuilds or requalifies an image. It
   serializes each image once into a private `dir:` transport. Authenticated preflight checks
   every source and version tag for all roles before the first copy, accepting only an absent tag
   or the exact intended digest. Skopeo then copies those exact staged bytes and verifies every
   remote digest. A later copy failure may leave a partial set, but the retained staging artifact
   is sufficient for the bounded recovery path below; neither normal publication nor recovery
   rebuilds an image. The workflow then generates provenance and attaches all three SBOM sets,
   publication receipts, and matched evidence to the verified Release identity. Because job
   credentials are isolated, the attestation job performs its own ephemeral GHCR login immediately
   before pushing provenance; it does not reuse or persist the publication job's credentials.

### Weekly release qualification

The **Release qualification dry-run** workflow runs on `main` every Monday at 05:17 UTC. To
check a suspected regression or verify a fix, run
`gh workflow run release-qualification-dry-run.yml --ref main`. Qualification and failure
reporting require `main`.

The dry-run uses the same final-image builds, smoke tests, SBOM checks, Critical-vulnerability
gate, and E2E shards as the release. A fresh runner and a run-local engine cache force the
upstream downloads. The scanner fetches a fresh Grype database. Image archives transfer within
the run. The dry-run creates no Git tag, GitHub Release, PyPI upload, GHCR push, attestation, or
publication receipt.

If qualification fails, follow its run from the `ci-main-failure` issue and restore green
qualification on `main` before resuming feature work. A successful dry-run clears the dry-run
failure in that issue. The reporting job checks prior successful dry-runs before recording a
failure so an older rerun cannot raise a stale alert.

### Post-release adoption

After the version pull request is merged, suspend unrelated integrations and monitor the automatic
release workflow on `main` to a terminal result. After both publications succeed, the
`adopt-receipts` job checks the public PyPI version, reads the three registry receipts attached to
the exact GitHub Release, and checks their bindings in `release-images.json` against the source SHA
and frontend lockfile. It verifies every tag anonymously against GHCR before updating the backend
and frontend pins in Compose, both quickstarts, and their test expectations. The reverse-attempt
receipt is verified and included in the pull request evidence for
[native-broker deployments](reverse-broker-deployment.md).

Run the `gh pr create` command printed in the job summary to open `chore/adopt-release-<version>`
against `main`. The branch CI dispatch provides evidence. Opening the pull request triggers normal
PR CI for the required `CI / gate` check. Complete any release-owned quickstart command migration
in the same pull request and run the documented standalone and distributed quickstarts against the
exact pins. Obtain independent review and restore alignment before integrating unrelated work.

A failed or partial publication leaves no adoption branch and reports the publication results in
the summary. Rerunning the adoption job reuses an identical branch and dispatches CI if its commit
has no dispatch yet. A differing branch fails without being overwritten. To review the generated
diff, run the current tooling with `--repo` pointing to a clean checkout at the release source SHA.
For a release published before the rename, run this from an up-to-date `markweave` checkout so the
tooling uses the canonical GitHub endpoints:

```bash
uv run --locked python -m scripts.release.adopt_receipts \
  --repo /path/to/release-checkout --version VERSION --source-sha RELEASE_SOURCE_SHA --dry-run
```

If publication fails, investigate or use the bounded recovery path below. If a separate recovery
workflow completes publication, use the recovered evidence to prepare the follow-up manually.
Never pre-pin an unpublished image or infer its registry digest.

If GitHub loses a run before creating any job, first prove that every external release surface is
absent and attempt the normal, forced, and platform-advised cancellation or rerun paths. Record the
orphaned run ID. If GitHub still cannot close or rerun it, increment
`tool.markweave.release.attempt` by exactly one in a protected pull request without changing the
version. Keep the existing workflow concurrency group: a recovered pending run is serialized with
the retry, while atomic tag creation and exact-SHA verification prevent two source SHAs from both
passing publication if the platform revives the orphan unexpectedly.

The release orchestrator and reusable container workflow use the same trusted push context; they do
not depend on a Release event. Tags and Releases created with `GITHUB_TOKEN` therefore cannot cause
a duplicate publication run. Container evidence attachment verifies the tag and Release SHA before
using `--clobber`, making a retry of that attachment idempotent. Any pre-existing tag, Release, or
PyPI version blocks a fresh run rather than being silently reused. Investigate partial external
state before authorizing any manual recovery. Recovery must not rebuild any container: registry
serialization is not guaranteed to be byte-reproducible across hosted Podman versions. Run
`container-release.yml` from `main` with the exact existing version, `v<version>` tag, reviewed
source SHA, and the ID of a failed source run in which every `container-qualify` job succeeded and
the `container-qualify / supply-chain` job retained the exact pre-mutation staging artifact.

Before download, recovery verifies the source run's stable numeric repository ID and exact
workflow. The run must come from trusted `main` at a descendant of the release source and an
ancestor of the current trusted `main` workflow SHA. Recovery also checks that the run completed
every qualification job and the pre-mutation staging step successfully, and has one bounded,
non-expired artifact with matching repository/run metadata. It downloads by immutable
artifact ID, not name alone. It then validates the exact regular-file set, closed checksum bundle,
OCI archives and metadata relationships, publication receipts, release version/tag/source, and the
state of every public GHCR digest in the retained release set. The recovery job has scoped `packages: write` permission because
it may need to publish a missing role from the retained bytes; it preflights every role before
copying, accepts an already-correct role idempotently, and rejects any conflicting digest. Only
after all exact digests are public does it transfer the unchanged evidence into the recovery run.
Separate jobs attest those exact public digests and attach the evidence to the already verified
Release. Recovery has no OIDC permission, never enters the PyPI environment, and cannot invoke
either build or Python publication.

The dispatch shape is:

```bash
gh workflow run container-release.yml --ref main \
  -f artifact-run-id=FAILED_RUN_ID \
  -f version=VERSION \
  -f tag=vVERSION \
  -f source-sha=RELEASE_SOURCE_SHA
```

Before dispatch, re-query the run and artifact to prove that retention has not expired. Afterward,
verify the attestation and all Release attachments before treating recovery as complete. The
`0.3.0` evidence recovery was completed successfully; its historical run and artifact identifiers
are recorded in `tickets/T22-finalize-cicd.md`, not presented here as a reusable current command.

Every GHCR conflict observed during authenticated
preflight fails before a copy. Repository and workflow concurrency prevent the automation from
racing itself. GHCR does not provide a relied-upon conditional manifest creation primitive here,
so another principal with `packages: write` could still change a tag in the narrow interval between
inspection and copy; do not grant that permission outside the release workflow.

The retained OCI archive and registry serialization can have different manifest digests for the
same local image. `image-metadata.json` remains internally bound to `image.oci.tar` and its SBOM;
`registry-publication.json` records that archive digest beside the exact registry digest, reviewed
source SHA, and version. Provenance uses the registry digest produced by the staged `dir:` transport.

## Post-publication verification

For released version `<version>`:

- verify `https://pypi.org/project/markweave/<version>/` shows Apache-2.0 metadata, the exact wheel
  and sdist, and attestations;
- install the wheel into fresh Python 3.14 environments for the base package and every supported
  extra, then verify `from markweave import __version__`, the exact version, and the installed CLI;
- verify GHCR tag `<version>` in each of the three repositories resolves to its receipt digest
  and is anonymously pullable;
- verify provenance against the exact workflow and repository that signed the digest, and check
  the main SHA associated with the signing run;
- verify the GitHub tag `v<version>` targets the release source SHA and every release evidence file is
  attached to its published GitHub Release.

Preserve workflow URLs and immutable digests in the release record. Do not publish, replace, or
delete external release state outside this protected automation without explicit approval.

Historical schema-1 releases bind only backend and frontend. Their retained recovery evidence
remains valid for that pair, but cannot identify a reverse-attempt image or qualify a matched
reverse deployment. Current schema-2 releases require all three roles.

### Verify container provenance

Set `image` to the package from `release-images.json` and set `digest` and `source_sha` to the
registry manifest digest and release source SHA from the verified publication receipt. For releases
published from the renamed repository, verify each image with:

```bash
gh attestation verify "oci://$image@$digest" \
  --repo Guillaume-Lombardo/markweave \
  --cert-identity https://github.com/Guillaume-Lombardo/markweave/.github/workflows/container-release.yml@refs/heads/main \
  --source-ref refs/heads/main --source-digest "$source_sha"
```

For evidence from a manual recovery, use the attestation run's repository identity and pass its
main SHA as `--source-digest`. The publication receipt still records the release source SHA.

The 0.8.0 image set was signed before the rename. The following command binds each published
digest to its original certificate identity and source SHA. The same signing-time rule applies
when verifying earlier releases and historical PyPI attestations.

```bash
(
  set -e
  signing_repo=Guillaume-Lombardo/simple-md-to-docx-converter
  source_sha=1a3350712224d2234540274eef0366f12d425468
  for image in \
    ghcr.io/guillaume-lombardo/md-converter@sha256:4aa0beec3f9c493c4109c2be4edb6e9f3e943808bb6f48e39492176d2d2f2a48 \
    ghcr.io/guillaume-lombardo/md-converter-web@sha256:2558483c2fadd33aa6de627d4e56a535cdf4a2c615d4a86f325cb6905f6c5fe8 \
    ghcr.io/guillaume-lombardo/md-converter-reverse-attempt@sha256:9351d1180e2c893d1e821547f63f6b5f158b7b8813aba3bb3825053e9c9fbcbe
  do
    printf '%s\n' "$image"
    gh attestation verify "oci://$image" --bundle-from-oci --repo "$signing_repo" \
      --cert-identity "https://github.com/$signing_repo/.github/workflows/container-release.yml@refs/heads/main" \
      --source-ref refs/heads/main --source-digest "$source_sha" \
      --format json --jq '"Verified provenance attestations: \(length)"'
  done
)
```

## Frontend publication after T64

T64 established the two-image baseline described in this section. Schema-2 releases extend that
baseline with the reverse-attempt image and require verification of all three roles as described above.

The release workflow publishes the backend and frontend as one evidence-bound pair without
replacing the established trust model. The frontend package identity is
`ghcr.io/guillaume-lombardo/md-converter-web`; it shares the Markweave version, source SHA,
`v<version>` tag, GitHub Release, and protected human gate with the backend but has its own registry
manifest digest, SBOMs, scan report, archive-to-registry receipt, and provenance.

One release is deployable only when the PyPI artifact and every required image receipt agree on
version and source SHA, all public digests are anonymously readable, and the release evidence
manifest binds the applicable set plus the frontend lockfile digest. The release workflow builds
and serializes each final image once, runs the complete rootless acceptance matrix
against those exact staged bytes, and publishes the same bytes. It must not test one image and rebuild
another after legacy removal. If publication is partial, recover the missing image/evidence from
the retained exact staged bytes without rebuilding, or fail the release. Never pair an older
frontend with a newer backend, infer a digest, or use a mutable tag as rollback identity.

The post-publication adoption pull request pins both exact public manifest digests in Compose,
quickstarts, and deployment evidence before unrelated integration resumes. The existing GHCR
preflight, exact-copy verification, narrow external-writer race disclosure, permissions,
concurrency, provenance, attachment, and anonymous verification rules apply separately to each
package. See [the reviewed migration architecture](archive/nextjs-migration-architecture.md) for the image
baseline, staged cutover, and release-level rollback contract.

## Linux release-command cleanup

The host-side build and clean-install tools require Linux `prctl` child-subreaper support.
They temporarily adopt orphan descendants, reap only children in the command's new process group,
and restore the caller's previous subreaper setting. Calls through the release helper are serialized
because that setting is process-wide. These are dedicated release CLI processes, not application
worker supervisors; embedding them alongside unrelated orphan-producing workloads is unsupported.
Existing unrelated direct children retain their exit status for their own `Popen` owners.

A zombie has exited but still makes `killpg(group, 0)` succeed until its parent reaps it. Reaping
adopted zombies before probing the group avoids depending on CI or development-host PID 1 behavior.
Reaping uses bounded batches and deadline checks, so a continuous stream of exited descendants
cannot delay termination indefinitely. Live leftovers after a successful leader exit still fail the command. Timeout cleanup sends SIGTERM
to the entire group, then SIGKILL when necessary, with bounded leader waits and group polls. Failure
to adopt, inspect, signal, or reap remains an explicit safe release error; it is never downgraded to
a normal timeout. Commands must remain in their assigned process group; this helper is not a
containment boundary for untrusted programs that create new sessions.

`uv run pytest tests/release --no-cov` covers the actual build/installation workflow and real
subprocess regressions. `tests/release/process_probe.py` is a dependency-free acceptance probe for
success, timeout, live leftovers, zombies, and injected cleanup failure. It also runs with the
reviewed source mounted read-only inside the final rootless Linux image:

```bash
podman run --rm --network=none --read-only --cap-drop=all \
  --security-opt=no-new-privileges --user=10042:0 --pids-limit=64 --memory=256m \
  --tmpfs=/tmp:rw,size=32m,mode=1777 --volume="$PWD:/verification:ro" \
  --workdir=/verification --entrypoint=python <verified-final-image-id> \
  -B -m tests.release.process_probe
```

This probe verifies the host release tooling on the final image's Linux/Python runtime; the tooling
is not included in the application image and does not change either storage profile.


## 0.6.4 adoption before the 0.7.0 transition

See the [historical release record](archive/evidence/release-migration-history.md#powerpoint-era-release-adoption).

## 0.7.0 publication and image adoption

See the [historical release record](archive/evidence/release-migration-history.md#powerpoint-era-release-adoption).

## 0.7.1 publication and image adoption

See the [historical release record](archive/evidence/release-migration-history.md#powerpoint-era-release-adoption).

## Related guidance

The [changelog](../CHANGELOG.md) records released behavior, while the
[upgrade guide](upgrading.md) and [recovery guide](recovery.md) define operator transitions and
rollback. Use the [container deployment guide](container-deployment.md) for immutable image
consumption, the [security policy](../SECURITY.md) for private vulnerability reports, and the
[support policy](../SUPPORT.md) for published-release help.
