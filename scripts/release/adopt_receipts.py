"""Prepare the public image pins from an already published Markweave release."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from packaging.version import Version

from scripts.container.release_pair import (
    CURRENT_SCHEMA_VERSION,
    IMAGE_DIRECTORIES,
    PAIR_MANIFEST,
)
from scripts.release import public_alignment as public

if TYPE_CHECKING:
    from collections.abc import Sequence

PIN_FILES = {
    "compose.yaml": (1, 2),
    "scripts/quickstart.sh": (1, 1),
    "scripts/quickstart-simple.sh": (1, 1),
    "scripts/e2e/run-compose-podman-insecure.sh": (1, 1),
    "tests/test_quickstart_compose.py": (1, 1),
    "tests/integration/test_compose_configuration.py": (1, 1),
}
GITHUB_REPOSITORY_URL = f"https://github.com/{public.REPOSITORY}"
GIT_NO_MATCHING_REF = 2


@dataclass(frozen=True)
class Publication:
    version: str
    source_sha: str
    digests: dict[str, str]

    @property
    def branch(self) -> str:
        return f"chore/adopt-release-{self.version}"


def verify_publication(
    transport: public.Transport, root: Path, *, version: str, source_sha: str
) -> Publication:
    """Require PyPI, the Release and all anonymous GHCR tags to agree."""
    if version != public.parse_project_version((root / "pyproject.toml").read_bytes()):
        raise public.AlignmentError("requested version differs from project.version")
    if version != public._pypi_version(transport):
        raise public.AlignmentError("PyPI has not published this as its latest version")
    release_sha, assets = public._release_identity(transport, version=version)
    if release_sha != source_sha:
        raise public.AlignmentError(
            "published Release differs from the reviewed source SHA"
        )
    manifest, _ = public._release_asset(
        transport,
        version=version,
        assets=assets,
        name=PAIR_MANIFEST,
        maximum_bytes=public.MAX_JSON_BYTES,
    )
    images = manifest.get("images")
    lock_sha = hashlib.sha256((root / "pnpm-lock.yaml").read_bytes()).hexdigest()
    if (
        manifest.get("schema_version") != CURRENT_SCHEMA_VERSION
        or manifest.get("version") != version
        or manifest.get("source_sha") != source_sha
        or manifest.get("frontend_lock_sha256") != lock_sha
        or not isinstance(images, dict)
        or images.keys() != IMAGE_DIRECTORIES.keys()
    ):
        raise public.AlignmentError(
            "release image manifest does not bind the complete reviewed image set"
        )
    digests: dict[str, str] = {}
    for role, package in IMAGE_DIRECTORIES.items():
        receipt, raw_receipt = public._release_asset(
            transport,
            version=version,
            assets=assets,
            name=f"{role}-registry-publication.json",
            maximum_bytes=public.MAX_RECEIPT_BYTES,
        )
        digest = public._receipt_digest(receipt, source_sha=source_sha, version=version)
        image = images[role]
        if not isinstance(image, dict) or (
            image.get("package"),
            image.get("receipt_sha256"),
            image.get("registry_manifest_digest"),
        ) != (package, hashlib.sha256(raw_receipt).hexdigest(), digest):
            raise public.AlignmentError(
                f"release image manifest does not bind the {role} receipt"
            )
        if (
            public._ghcr_digest(
                transport,
                version=version,
                repository_path=package.removeprefix("ghcr.io/"),
            )
            != digest
        ):
            raise public.AlignmentError(
                f"anonymous GHCR digest differs from the {role} receipt"
            )
        digests[role] = digest
    return Publication(version, source_sha, digests)


def pin_updates(root: Path, publication: Publication) -> dict[str, tuple[str, str]]:
    """Replace the matched public defaults while preserving surrounding source text."""
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    backend = public.parse_compose_identity(compose)
    frontend = public.parse_frontend_compose_identity(compose)
    if backend.version != frontend.version or Version(backend.version) > Version(
        publication.version
    ):
        raise public.AlignmentError(
            "Compose must start from a matched, non-newer release"
        )
    updates = {}
    for name, counts in PIN_FILES.items():
        before = (root / name).read_text(encoding="utf-8")
        after = before
        for role, old, expected_count in zip(
            ("backend", "frontend"), (backend, frontend), counts, strict=True
        ):
            package = re.escape(IMAGE_DIRECTORIES[role])
            # Test constants split the reference into adjacent Python strings.
            pin = re.compile(
                rf'{package}:{re.escape(old.version)}@(?P<separator>"\n +")?{re.escape(old.digest)}'
            )
            after, count = pin.subn(
                lambda match, role=role: (
                    f"{IMAGE_DIRECTORIES[role]}:{publication.version}@"
                    f"{match.group('separator') or ''}{publication.digests[role]}"
                ),
                after,
            )
            if count != expected_count:
                raise public.AlignmentError(
                    f"{name} has {count} matching {role} pins, expected {expected_count}"
                )
        if before != after:
            updates[name] = before, after
    return updates


def _git(
    root: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed executable and validated refs
        ["/usr/bin/git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _remote_branch(root: Path, ref: str) -> bool:
    result = _git(
        root, "ls-remote", "--exit-code", "--refs", "origin", ref, check=False
    )
    if result.returncode == GIT_NO_MATCHING_REF:
        return False
    result.check_returncode()
    return True


def push_branch(
    root: Path, publication: Publication, updates: dict[str, tuple[str, str]]
) -> str | None:
    """Create a single-commit branch, or reuse its exact existing tree."""
    if not updates:
        return None
    ref = f"refs/heads/{publication.branch}"
    for name, (_, after) in updates.items():
        (root / name).write_text(after, encoding="utf-8")
    _git(root, "add", "--", *updates)
    tree = _git(root, "write-tree").stdout.strip()

    if not _remote_branch(root, ref):
        commit = _git(
            root,
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit-tree",
            tree,
            "-p",
            publication.source_sha,
            "-m",
            f"chore: adopt verified {publication.version} image receipts",
        ).stdout.strip()
        # An empty lease is a create-only compare-and-set. It cannot update an existing ref.
        push = _git(
            root,
            "push",
            f"--force-with-lease={ref}:",
            "origin",
            f"{commit}:{ref}",
            check=False,
        )
        if push.returncode == 0:
            return commit
        if not _remote_branch(root, ref):
            push.check_returncode()

    _git(root, "fetch", "--no-tags", "origin", ref)
    identity = _git(
        root, "show", "-s", "--format=%H %T %P", "FETCH_HEAD"
    ).stdout.split()
    if identity[1:] != [tree, publication.source_sha]:
        raise public.AlignmentError(
            f"existing adoption branch {publication.branch} differs from the verified release changes"
        )
    return identity[0]


def _gh(*args: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed CLI and validated arguments
        ["gh", *args, "--repo", public.REPOSITORY],  # noqa: S607 - hosted runner CLI
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def dispatch_ci(publication: Publication, commit: str) -> None:
    """Dispatch CI once it has no evidence for the adoption commit."""
    if not _gh(
        "run",
        "list",
        "--workflow",
        "ci.yml",
        "--branch",
        publication.branch,
        "--commit",
        commit,
        "--event",
        "workflow_dispatch",
        "--limit",
        "1",
        "--json",
        "url",
        "--jq",
        ".[0].url // empty",
    ):
        _gh("workflow", "run", "ci.yml", "--ref", publication.branch)


def _summary(publication: Publication, *, release_run_url: str) -> str:
    version = publication.version
    branch = publication.branch
    tag_url = f"{GITHUB_REPOSITORY_URL}/releases/tag/v{version}"
    query = urlencode({"query": f"branch:{branch} event:workflow_dispatch"})
    ci_url = f"{GITHUB_REPOSITORY_URL}/actions/workflows/ci.yml?{query}"
    body = "\n".join(
        [
            f"Adopt the verified public image receipts for Markweave {version} from `{publication.source_sha}`.",
            "",
            f"[Publication run]({release_run_url}) · [GitHub Release and receipts]({tag_url}) · "
            f"[PyPI](https://pypi.org/project/markweave/{version}/) · [Dispatched branch CI]({ci_url})",
            "",
            *(
                f"- {role}: `{IMAGE_DIRECTORIES[role]}:{version}@{digest}`"
                for role, digest in publication.digests.items()
            ),
        ]
    )
    command = shlex.join(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            public.REPOSITORY,
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            f"chore: adopt verified {version} image receipts",
            "--body",
            body,
        ]
    )
    return (
        "### Release receipt adoption\n\n"
        f"Verified publication and prepared `{branch}`. Open the adoption pull request with:\n\n"
        f"```sh\n{command}\n```\n\n"
        "The branch dispatch provides evidence. Opening the pull request triggers normal PR CI "
        "for the required `CI / gate` check.\n"
    )


def _write_summary(message: str) -> None:
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")
    print(message)


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify publication and print the diff without writing pins or pushing.",
    )
    args = parser.parse_args(arguments)
    try:
        if (
            not public.FULL_SHA.fullmatch(args.source_sha)
            or args.source_sha != _git(args.repo, "rev-parse", "HEAD").stdout.strip()
        ):
            raise public.AlignmentError(
                "checkout differs from the reviewed release source SHA"
            )
        if _git(args.repo, "status", "--porcelain", "--untracked-files=no").stdout:
            raise public.AlignmentError("adoption requires a clean tracked checkout")
        publication = verify_publication(
            public.UrlLibTransport(github_token=os.environ.get("GH_TOKEN")),
            args.repo,
            version=args.version,
            source_sha=args.source_sha,
        )
        updates = pin_updates(args.repo, publication)
        if args.dry_run:
            for name, (before, after) in updates.items():
                sys.stdout.writelines(
                    difflib.unified_diff(
                        before.splitlines(keepends=True),
                        after.splitlines(keepends=True),
                        f"a/{name}",
                        f"b/{name}",
                    )
                )
            return 0

        if (
            not (run_id := os.environ.get("GITHUB_RUN_ID", "")).isascii()
            or not run_id.isdecimal()
        ):
            raise public.AlignmentError(
                "GITHUB_RUN_ID is required to publish adoption evidence"
            )
        commit = push_branch(args.repo, publication, updates)
        if commit is None:
            _write_summary(
                "### Release receipt adoption\n\nThe reviewed source already uses the verified pins."
            )
        else:
            dispatch_ci(publication, commit)
            _write_summary(
                _summary(
                    publication,
                    release_run_url=f"{GITHUB_REPOSITORY_URL}/actions/runs/{run_id}",
                )
            )
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr.rstrip(), file=sys.stderr)
        _write_summary(f"### Release receipt adoption failed\n\n{error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
