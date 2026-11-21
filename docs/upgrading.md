<a id="upgrading"></a>

# Upgrading

This guide defines the supported operator path between released Markweave
versions. It covers a package installation and the matching container image;
it does not choose production limits, retention values, or a deployment
topology.

## Supported transition

<a id="supported-transition"></a>

Upgrade only from one released final version to a later released final version.
Keep all application components that access one database at the same Markweave
version. For a container deployment, use the image bearing that exact release
version; for a package deployment, install the wheel with that same version.
Do not combine a new wheel with an older image, or an older wheel with a newer
image, against one live database.

Read the target release entry in [the changelog](../CHANGELOG.md#changelog)
and the target release's published evidence before scheduling the change. Test
the exact source, image, and configuration in an isolated environment that
matches the selected storage profile before production use.

Select a complete published release with verified receipts for every required image. Version `0.7.2`
has no qualified published container set; see the [incident record](archive/evidence/release-migration-history.md#incomplete-072-container-release).
Version `0.7.4` was published to PyPI only and has no container images; container deployments
upgrade from `0.7.3` directly to `0.7.5`. See the
[0.7.4 incident record](archive/evidence/release-migration-history.md#incomplete-074-container-release).
The repository quickstarts pin the matched published `0.7.5` backend/frontend images. Reverse-enabled
deployments also require the matching reverse-attempt image and native broker.

## Upgrade procedure

<a id="upgrade-procedure"></a>

1. Select the target released version and confirm its package and container
   provenance. Record the current version, image digest, configuration source,
   and database revision.
2. Verify that every required `MARKWEAVE_*` setting is present for the selected
   profile. For 0.8.0 and later, apply the [configuration migration](#configuration-compatibility).
   Do not substitute unresolved production-limit placeholders with values invented during an upgrade.
3. Create and verify a profile-consistent backup before changing binaries or
   schema. For standalone, preserve the SQLite database and the complete object
   directory together. For distributed, preserve the PostgreSQL recovery point
   and matching object-store versions from one coordinated window.
4. Stop or drain every API and worker process that can write the selected
   profile. Never run a mixed-version fleet during a schema transition.
5. Deploy the target package or exact container image, then start one controlled
   Markweave application component for the selected profile. Alembic upgrades
   older metadata when that component is assembled; wait for its migration and
   readiness result before starting any other component at the target version.
   This guide does not depend on a separate migration command.
6. Require `/health/ready` from the controlled component before admitting
   traffic. Start the remaining same-version components only after readiness,
   then verify representative stable object identifiers and one authorized
   workflow before ending the maintenance window.

## Schema changes and rollback

<a id="schema-and-rollback"></a>

Migrations move the database forward. A backup made before the migration is the
rollback boundary; do not assume an automatic schema downgrade exists. If the
target version fails after its migration starts, keep traffic stopped, restore
the database and its matching object data into isolated targets, validate the
restore, then return all components to the previously released version.

A recovery set created before an upgrade remains restorable by the newer release. `markweave
restore` verifies the set against the schema revision recorded in it, then migrates the restored
database to the newer head. Supported sets come from release 0.5.0 or later, starting at schema
revision `20260829_14`; a set from a newer release is refused. A distributed set that contains a
retained conversion job referencing a superseded template version cannot be restored yet; this
limitation is tracked as T132 (G1L-685). See
[recovery sets from earlier releases](recovery.md#recovery-sets-from-earlier-releases).

Do not restore a database without its corresponding object state, and do not
point a restored database at a newer or unrelated object-store version. A
rollback is complete only after readiness and representative stable-object
checks succeed on the restored previous version.

### Reverse-conversion migration 19

Migration 19 persists reverse-extraction options. When the source database revision predates Migration 19,
create and verify the profile-consistent database and object backup required above, record the
running broker configuration and native-broker package/virtual environment, and drain reverse work.
Keep the application, frontend, reverse-attempt images, and native-broker executable at the same
target release version and bind the three images to one verified schema-2 `release-images.json`.

The reverse broker remains a host-native, externally isolated service; do not replace it with a
container. Ordinary quickstarts do not configure the external broker. Configure its immutable
attempt-image digest only from the verified release manifest, then require broker `READY` and one
authenticated reverse smoke workflow before reopening reverse admission. Follow the current published
quickstart and release receipts when selecting public image pins.

If migration 19 or the matched reverse set fails, stop admission, restore the pre-upgrade database
and object backup into isolated targets, restore the prior application/frontend/reverse image set,
native-broker executable/virtual environment, and broker configuration together, then verify
readiness before returning traffic. Do not mix a new broker policy or attempt image with a restored
older application release.

### Next.js cutover releases

Current releases use separate backend and frontend images. Upgrade and roll back the matched image
set and routing manifest together; verify frontend routes, FastAPI readiness, login and an authorized
workflow before restoring traffic. Restore the matching database and object backup if persistent
state changed. The one-time legacy-renderer migration and its old rollback procedure are retained
in [cutover history](archive/evidence/release-migration-history.md#nextjs-cutover-and-legacy-rollback).

### Upgrading to 0.7.5

Release 0.7.5 supersedes 0.7.4. Version 0.7.4 was published to PyPI, but its container release
stopped at the Critical-vulnerability gate before any image was published, so no `0.7.4` image
exists. Container deployments upgrade from `0.7.3` directly to `0.7.5`. Package deployments may
upgrade from `0.7.3` or `0.7.4`; 0.7.5 keeps the 0.7.4 database schema and adds no migration.

Compared with 0.7.3, release 0.7.5 adds Composer migrations 20 to 26. Follow the upgrade procedure
above: create and verify the profile-consistent backup, drain every component, and let one
controlled `0.7.5` component apply the migrations and report readiness before starting the others.
There is no automatic downgrade; to return to `0.7.3` after the migrations start, restore the
pre-upgrade database and object backup and the matched `0.7.3` backend/frontend images together.
Composer model access remains disabled unless `MARKWEAVE_COMPOSER_ENABLED=true` and its policy
settings are configured, so an upgrade needs no new setting.

`markweave restore` in 0.7.5 accepts recovery sets created by release 0.5.0 or later, from schema
revision `20260829_14`, and migrates them to the 0.7.5 head. Sets from earlier revisions, unknown
revisions or a newer release are refused. Keep a `0.7.3` recovery set until the upgraded
deployment is verified.

The Compose quickstart files are consolidated. The Next.js browser tier is now part of
`compose.yaml`, and the Podman browser settings are part of `compose.podman.yaml` and
`compose.podman-trusted-upstream.yaml`. `compose.nextjs.yaml`, `compose.nextjs-podman.yaml` and
`compose.nextjs-podman-trusted-upstream.yaml` no longer exist. The `scripts/quickstart.sh` and
`scripts/quickstart-simple.sh` helpers need no change. If you combine Compose files by hand, remove
the deleted files from your `-f` list; every supported mode renders the same configuration as
before. The image override variables `MARKWEAVE_CUTOVER_BACKEND_IMAGE` and
`MARKWEAVE_CUTOVER_FRONTEND_IMAGE` are unchanged.

Protected release run `38223418529` published the matched schema-2 `0.7.5` backend, frontend and
reverse-attempt images from source `d54a9c5f9440205bc415e7a49c4583f502392c29`. The repository
Compose file and quickstarts now pin the exact verified `0.7.5` receipts: backend
`sha256:237597e5aee89a744f29027e3ad0e10845296f435da8902d1ee5af2b7f591677` and frontend
`sha256:f628055556c61b04cfbd3202e32464ad38719d7b057ea87ed9b249e44c6d01ce`. Reverse-enabled
deployments configure the native broker with the reverse-attempt digest
`sha256:104d35de4f75459ed5bab4583a5fc472d521247cc23a339ed9b8995296ec97bc`. Existing deployments
keep their verified `0.7.3` configuration until they adopt these exact pins and complete
deployment-specific verification. Do not run a `0.7.4` or `0.7.5` package against `0.7.3` images
or invent a `0.7.4` image digest.

## Upgrading to 0.8.0

### Reverse isolation in 0.8.0

Version 0.8.0 removes the experimental `markweave[kubernetes]` extra and
`markweave-kubernetes-attester` executable. Remove both from installation and startup automation.
For reverse conversion, configure the [rootless Podman broker](reverse-broker-deployment.md) and
one of its authenticated transports. The broker rejects old Kubernetes configuration. T74's
prototype is preserved in the `archive/t74-kubernetes-backend` Git tag.

<a id="configuration-compatibility"></a>

### Configuration compatibility

Version 0.8.0 removes the deprecated `MD_CONVERTER_*` aliases. Before starting the
new version, rename each former alias in environment files, service definitions,
Compose overrides, and deployment manifests. Keep its value and remove the old name
from the process environment. If both names are present, verify the canonical value
and remove the alias. Even an empty alias prevents startup. The error names each
replacement and omits values.

| Previous name | Canonical name |
| --- | --- |
| `MD_CONVERTER_<SUFFIX>` (every former alias) | `MARKWEAVE_<SUFFIX>` (same suffix) |
| `MD_CONVERTER_HOST` | `MARKWEAVE_HOST` |
| `MD_CONVERTER_PORT` | `MARKWEAVE_PORT` |
| `MD_CONVERTER_INITIAL_ADMIN_PASSWORD` | `MARKWEAVE_INITIAL_ADMIN_PASSWORD` |
| `MD_CONVERTER_STANDALONE_DATA_DIRECTORY` | `MARKWEAVE_STANDALONE_DATA_DIRECTORY` |
| `MD_CONVERTER_DISTRIBUTED_DATABASE_URL` | `MARKWEAVE_DISTRIBUTED_DATABASE_URL` |
| `MD_CONVERTER_S3_BUCKET` | `MARKWEAVE_S3_BUCKET` |

The repository Compose files already use canonical names. Check any local overrides
before upgrading either storage profile or a local conversion environment.

## Stable links

- [Upgrade guide top](#upgrading)
- [Supported transition](#supported-transition)
- [Upgrade procedure](#upgrade-procedure)
- [Schema changes and rollback](#schema-changes-and-rollback)
- [Upgrading to 0.7.5](#upgrading-to-075)
- [Configuration migration for 0.8.0](#configuration-compatibility)

## Related guidance

Read the [changelog](../CHANGELOG.md) for the exact source release, the
[configuration reference](configuration.md) for accepted settings, and the
[recovery guide](recovery.md) before changing persistent state. The
[container deployment guide](container-deployment.md) and [release process](releasing.md) define
immutable image and publication evidence. The [security policy](../SECURITY.md) and
[support policy](../SUPPORT.md) define the supported release boundary.
