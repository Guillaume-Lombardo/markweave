"""Verify receipt-bound pin generation and branch retry behavior."""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from pathlib import Path

import pytest

from scripts.release import adopt_receipts as adoption
from scripts.release import public_alignment as public
from tests.release.test_public_alignment import FakeTransport, _json_response

SOURCE = "a" * 40
VERSION = "0.8.0"
BRANCH = f"chore/adopt-release-{VERSION}"
RELEASE_API = f"{public.GITHUB_API}/releases/tags/v{VERSION}"
ASSET_URL = f"{public.GITHUB_RELEASES}/v{VERSION}"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def checkout(tmp_path):
    paths = ("backend", "frontend")
    images = [
        (adoption.IMAGE_DIRECTORIES[role], f"sha256:{letter * 64}")
        for role, letter in zip(paths, "cd", strict=True)
    ]
    for name in adoption.PIN_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        references = [f"{package}:0.7.5@{digest}" for package, digest in images]
        if name == "compose.yaml":
            before = (
                "services:\n"
                f'  markweave:\n    image: "${{MARKWEAVE_CUTOVER_BACKEND_IMAGE:-{references[0]}}}"\n'
                f'  frontend:\n    image: "${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{references[1]}}}"\n'
                f'  router:\n    image: "${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{references[1]}}}"\n'
            )
        elif name.endswith(".py"):
            before = "".join(
                f'{role.upper()} = (\n    "{package}:0.7.5@"\n    "{digest}"\n)\n'
                for role, (package, digest) in zip(paths, images, strict=True)
            )
        else:
            before = "".join(
                f'readonly {role}_image="{pin}"\n'
                for role, pin in zip(paths, references, strict=True)
            )
        path.write_text(before)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{VERSION}"\n')
    (tmp_path / "pnpm-lock.yaml").write_bytes(b"verified lock contents\n")
    return tmp_path


@pytest.fixture
def published():
    def fixture(source=SOURCE):
        roles = adoption.IMAGE_DIRECTORIES
        names = [
            "release-images.json",
            *(f"{role}-registry-publication.json" for role in roles),
        ]
        responses = {
            public.PYPI_URL: _json_response({"info": {"version": VERSION}}),
            RELEASE_API: _json_response(
                {
                    "tag_name": f"v{VERSION}",
                    "target_commitish": source,
                    "draft": False,
                    "prerelease": False,
                    "published_at": "published",
                    "assets": [
                        {"name": name, "browser_download_url": f"{ASSET_URL}/{name}"}
                        for name in names
                    ],
                }
            ),
            f"{public.GITHUB_API}/git/ref/tags/v{VERSION}": _json_response(
                {"object": {"type": "commit", "sha": source}}
            ),
        }
        images = {}
        for role, package in roles.items():
            manifest = json.dumps(
                {"schemaVersion": 2, "config": {"role": role}}
            ).encode()
            digest = f"sha256:{hashlib.sha256(manifest).hexdigest()}"
            repo = package.removeprefix("ghcr.io/")
            responses[
                f"https://ghcr.io/token?service=ghcr.io&scope=repository:{repo}:pull"
            ] = _json_response({"token": "anonymous-pull-token"})
            responses[f"https://ghcr.io/v2/{repo}/manifests/{VERSION}"] = (
                public.HttpResponse(200, {"docker-content-digest": digest}, manifest)
            )
            receipt = _json_response(
                {
                    "oci_archive_manifest_digest": f"sha256:{'b' * 64}",
                    "registry_manifest_digest": digest,
                    "source_sha": source,
                    "version": VERSION,
                }
            )
            responses[f"{ASSET_URL}/{role}-registry-publication.json"] = receipt
            images[role] = {
                "package": package,
                "registry_manifest_digest": digest,
                "receipt_sha256": hashlib.sha256(receipt.body).hexdigest(),
            }
        responses[f"{ASSET_URL}/release-images.json"] = _json_response(
            {
                "schema_version": 2,
                "version": VERSION,
                "source_sha": source,
                "images": images,
                "frontend_lock_sha256": hashlib.sha256(
                    b"verified lock contents\n"
                ).hexdigest(),
            }
        )
        return FakeTransport(responses), {
            role: image["registry_manifest_digest"] for role, image in images.items()
        }

    return fixture


@pytest.mark.unit
def test_receipts_generate_exact_aligned_pins(checkout, published):
    transport, digests = published()
    publication = adoption.verify_publication(
        transport, checkout, version=VERSION, source_sha=SOURCE
    )
    assert publication.digests == digests
    assert all(
        "Authorization" not in headers
        for url, headers in transport.requests
        if url.startswith("https://ghcr.io/token")
    )
    updates = adoption.pin_updates(checkout, publication)
    assert updates.keys() == adoption.PIN_FILES.keys()
    for name, (before, after) in updates.items():
        removed = [
            line for line in before.splitlines() if line not in after.splitlines()
        ]
        added = [line for line in after.splitlines() if line not in before.splitlines()]
        assert (
            len(removed)
            == len(added)
            == (4 if name.endswith(".py") else 3 if name == "compose.yaml" else 2)
        )
        assert sum(line.count(digests["backend"]) for line in added) == 1
        assert sum(line.count(digests["frontend"]) for line in added) == (
            2 if name == "compose.yaml" else 1
        )
        (checkout / name).write_text(after)
    updated = updates["compose.yaml"][1]
    assert (
        public.check_alignment(
            project_version=VERSION,
            event_name="workflow_dispatch",
            transport=transport,
            compose=public.parse_compose_identity(updated),
            frontend=public.parse_frontend_compose_identity(updated),
        )
        == "aligned"
    )
    assert adoption.pin_updates(checkout, publication) == {}


@pytest.mark.unit
def test_repository_public_pin_layout_matches_generator() -> None:
    compose = (ROOT / "compose.yaml").read_text()
    backend = public.parse_compose_identity(compose)
    frontend = public.parse_frontend_compose_identity(compose)
    publication = adoption.Publication(
        backend.version,
        SOURCE,
        {"backend": backend.digest, "frontend": frontend.digest},
    )
    assert adoption.pin_updates(ROOT, publication) == {}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "response", "match"),
    [
        (
            public.PYPI_URL,
            _json_response({"info": {"version": "0.7.5"}}),
            "PyPI has not published",
        ),
        (
            f"{ASSET_URL}/release-images.json",
            _json_response({}),
            "complete reviewed image set",
        ),
        (
            f"{ASSET_URL}/reverse_attempt-registry-publication.json",
            public.HttpResponse(404, {}, b""),
            "invalid response",
        ),
        (
            f"{ASSET_URL}/backend-registry-publication.json",
            _json_response({}),
            "invalid shape",
        ),
        (
            f"https://ghcr.io/v2/{public.REVERSE_REGISTRY_PATH}/manifests/{VERSION}",
            public.HttpResponse(404, {}, b""),
            "no immutable digest",
        ),
    ],
)
def test_incomplete_publication_fails_before_branch_creation(  # noqa: PLR0913 - fixtures and failure cases
    *, checkout, published, mocker, monkeypatch, url, response, match
):
    transport, _ = published()
    transport.responses[url] = response
    mocker.patch.object(public, "UrlLibTransport", return_value=transport)
    mocker.patch.object(
        adoption,
        "_git",
        side_effect=[mocker.Mock(stdout=SOURCE), mocker.Mock(stdout="")],
    )
    push = mocker.patch.object(adoption, "push_branch")
    summary = checkout / "summary"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert (
        adoption.main(
            ["--repo", str(checkout), "--version", VERSION, "--source-sha", SOURCE]
        )
        == 1
    )
    push.assert_not_called()
    assert match in summary.read_text()


@pytest.mark.unit
def test_manifest_must_bind_exact_receipt_bytes(checkout, published):
    transport, _ = published()
    url = f"{ASSET_URL}/frontend-registry-publication.json"
    receipt = transport.request(url, headers={})
    transport.responses[url] = public.HttpResponse(200, {}, receipt.body + b"\n")
    with pytest.raises(
        public.AlignmentError, match="does not bind the frontend receipt"
    ):
        adoption.verify_publication(
            transport, checkout, version=VERSION, source_sha=SOURCE
        )


@pytest.mark.unit
def test_dry_run_prints_diff_without_writing_or_pushing(
    checkout, published, mocker, capsys
):
    transport, digests = published()
    mocker.patch.object(public, "UrlLibTransport", return_value=transport)
    mocker.patch.object(
        adoption,
        "_git",
        side_effect=[mocker.Mock(stdout=SOURCE), mocker.Mock(stdout="")],
    )
    push = mocker.patch.object(adoption, "push_branch")
    before = (checkout / "compose.yaml").read_bytes()
    result = adoption.main(
        [
            "--repo",
            str(checkout),
            "--version",
            VERSION,
            "--source-sha",
            SOURCE,
            "--dry-run",
        ]
    )
    assert result == 0
    diff = capsys.readouterr().out
    assert "+++ b/compose.yaml" in diff
    assert f"{VERSION}@{digests['backend']}" in diff
    assert (checkout / "compose.yaml").read_bytes() == before
    push.assert_not_called()


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.integration
def test_push_dispatch_retry_and_differing_branch(
    checkout, published, mocker, monkeypatch, capsys
):
    checkout = checkout.resolve()
    remote = checkout / "remote.git"
    remote.mkdir()
    git(remote, "init", "--bare")
    git(checkout, "init")
    git(checkout, "remote", "add", "origin", str(remote))
    git(checkout, "add", *adoption.PIN_FILES, "pyproject.toml", "pnpm-lock.yaml")
    git(
        checkout,
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release@example.test",
        "commit",
        "-m",
        "Review source",
    )
    source = git(checkout, "rev-parse", "HEAD")
    transport, digests = published(source)
    mocker.patch.object(public, "UrlLibTransport", return_value=transport)
    gh = mocker.patch.object(adoption, "_gh", side_effect=["", "", "existing-ci-run"])
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    args = ["--repo", str(checkout), "--version", VERSION, "--source-sha", source]
    ref = f"refs/heads/{BRANCH}"

    assert adoption.main(args) == 0
    commit = git(remote, "rev-parse", ref)
    assert git(remote, "rev-parse", f"{ref}^") == source
    assert (
        set(git(remote, "diff", "--name-only", source, commit).splitlines())
        == adoption.PIN_FILES.keys()
    )
    assert gh.call_args.args == ("workflow", "run", "ci.yml", "--ref", BRANCH)
    summary = capsys.readouterr().out
    command = shlex.split(summary.split("```sh\n", 1)[1].split("\n```", 1)[0])
    assert command[:3] == ["gh", "pr", "create"]
    assert command[command.index("--base") + 1] == "main"
    assert command[command.index("--head") + 1] == BRANCH
    assert "actions/runs/123" in command[-1]
    assert all(digest in command[-1] for digest in digests.values())
    assert "CI / gate" in summary

    git(checkout, "reset", "--hard", source)
    assert adoption.main(args) == 0
    assert git(remote, "rev-parse", ref) == commit
    assert gh.call_count == 3
    assert gh.call_args.args[:2] == ("run", "list")

    git(checkout, "reset", "--hard", source)
    other = git(
        remote,
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release@example.test",
        "commit-tree",
        f"{commit}^{{tree}}",
        "-p",
        commit,
        "-m",
        "Different branch",
    )
    git(remote, "update-ref", ref, other, commit)
    assert adoption.main(args) == 1
    assert "differs from the verified release changes" in capsys.readouterr().out
    assert git(remote, "rev-parse", ref) == other
    assert gh.call_count == 3
