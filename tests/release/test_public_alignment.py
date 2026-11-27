"""Tests for fail-closed public package and image alignment."""

from __future__ import annotations

import hashlib
import io
import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import Message
from pathlib import Path

import pytest

from scripts.release import public_alignment
from scripts.release.public_alignment import (
    AlignmentError,
    BaseIdentity,
    ComposeIdentity,
    HttpResponse,
    check_alignment,
    parse_compose_identity,
    parse_frontend_compose_identity,
    parse_project_version,
)

SOURCE_SHA = "a" * 40
REGISTRY_MANIFEST = b'{"schemaVersion":2,"config":{}}'
REGISTRY_DIGEST = f"sha256:{hashlib.sha256(REGISTRY_MANIFEST).hexdigest()}"


@dataclass
class FakeTransport:
    """Return exact fixtures while recording the fixed endpoint contract."""

    responses: dict[str, HttpResponse | list[HttpResponse]]

    def __post_init__(self) -> None:
        self.requests: list[tuple[str, dict[str, str]]] = []

    def request(self, url: str, *, headers) -> HttpResponse:
        self.requests.append((url, dict(headers)))
        try:
            response = self.responses[url]
            if isinstance(response, list):
                if not response:
                    raise AssertionError(f"exhausted responses for URL: {url}")
                return response.pop(0)
            return response
        except KeyError as error:
            raise AssertionError(f"unexpected URL: {url}") from error


def _json_response(value: object) -> HttpResponse:
    return HttpResponse(
        200, {"content-type": "application/json"}, json.dumps(value).encode()
    )


def _public_transport(*, version: str = "0.4.0") -> FakeTransport:
    tag = f"v{version}"
    receipt_url = f"{public_alignment.GITHUB_RELEASES}/{tag}/registry-publication.json"
    return FakeTransport(
        {
            public_alignment.PYPI_URL: _json_response({"info": {"version": version}}),
            f"{public_alignment.GITHUB_API}/releases/tags/{tag}": _json_response(
                {
                    "tag_name": tag,
                    "target_commitish": SOURCE_SHA,
                    "draft": False,
                    "prerelease": False,
                    "published_at": "2026-08-29T12:00:00Z",
                    "assets": [
                        {
                            "name": "registry-publication.json",
                            "browser_download_url": receipt_url,
                        }
                    ],
                }
            ),
            f"{public_alignment.GITHUB_API}/git/ref/tags/{tag}": _json_response(
                {"object": {"type": "commit", "sha": SOURCE_SHA}}
            ),
            receipt_url: _json_response(
                {
                    "oci_archive_manifest_digest": f"sha256:{'b' * 64}",
                    "registry_manifest_digest": REGISTRY_DIGEST,
                    "source_sha": SOURCE_SHA,
                    "version": version,
                }
            ),
            public_alignment.GHCR_TOKEN_URL: _json_response({"token": "pull-token"}),
            f"https://ghcr.io/v2/{public_alignment.REGISTRY_PATH}/manifests/{version}": HttpResponse(
                200,
                {"Docker-Content-Digest": REGISTRY_DIGEST},
                REGISTRY_MANIFEST,
            ),
        }
    )


def _paired_transport(*, version: str = "0.6.1") -> FakeTransport:
    tag = f"v{version}"
    transport = _public_transport(version=version)
    release_url = f"{public_alignment.GITHUB_API}/releases/tags/{tag}"
    release_response = transport.responses[release_url]
    assert isinstance(release_response, HttpResponse)
    release = json.loads(release_response.body)
    release["assets"] = []
    transport.responses[release_url] = _json_response(release)
    legacy_receipt = (
        f"{public_alignment.GITHUB_RELEASES}/{tag}/registry-publication.json"
    )
    del transport.responses[legacy_receipt]
    for role in ("backend", "frontend"):
        name = f"{role}-registry-publication.json"
        url = f"{public_alignment.GITHUB_RELEASES}/{tag}/{name}"
        release["assets"].append({"name": name, "browser_download_url": url})
        transport.responses[url] = _json_response(
            {
                "oci_archive_manifest_digest": f"sha256:{'b' * 64}",
                "registry_manifest_digest": REGISTRY_DIGEST,
                "source_sha": SOURCE_SHA,
                "version": version,
            }
        )
    transport.responses[release_url] = _json_response(release)
    frontend_token = (
        "https://ghcr.io/token?service=ghcr.io&scope=repository:"
        f"{public_alignment.FRONTEND_REGISTRY_PATH}:pull"
    )
    transport.responses[frontend_token] = _json_response({"token": "frontend-token"})
    transport.responses[
        f"https://ghcr.io/v2/{public_alignment.FRONTEND_REGISTRY_PATH}/manifests/{version}"
    ] = HttpResponse(200, {"Docker-Content-Digest": REGISTRY_DIGEST}, REGISTRY_MANIFEST)
    return transport


@pytest.mark.unit
def test_accepts_fully_aligned_public_release() -> None:
    transport = _public_transport()

    state = check_alignment(
        project_version="0.4.0",
        compose=ComposeIdentity("0.4.0", REGISTRY_DIGEST),
        event_name="schedule",
        transport=transport,
    )

    assert state == "aligned"
    assert [url for url, _headers in transport.requests] == [
        public_alignment.PYPI_URL,
        f"{public_alignment.GITHUB_API}/releases/tags/v0.4.0",
        f"{public_alignment.GITHUB_API}/git/ref/tags/v0.4.0",
        (f"{public_alignment.GITHUB_RELEASES}/v0.4.0/registry-publication.json"),
        public_alignment.GHCR_TOKEN_URL,
        f"https://ghcr.io/v2/{public_alignment.REGISTRY_PATH}/manifests/0.4.0",
    ]


@pytest.mark.unit
def test_accepts_paired_public_release_only_after_both_exact_receipts() -> None:
    transport = _paired_transport()
    identity = ComposeIdentity("0.6.1", REGISTRY_DIGEST)

    state = check_alignment(
        project_version="0.6.1",
        compose=identity,
        frontend=identity,
        event_name="schedule",
        transport=transport,
    )

    assert state == "aligned"
    requested = [url for url, _headers in transport.requests]
    assert (
        f"{public_alignment.GITHUB_RELEASES}/v0.6.1/backend-registry-publication.json"
        in requested
    )
    assert (
        f"{public_alignment.GITHUB_RELEASES}/v0.6.1/frontend-registry-publication.json"
        in requested
    )
    assert (
        f"https://ghcr.io/v2/{public_alignment.FRONTEND_REGISTRY_PATH}/manifests/0.6.1"
        in requested
    )


@pytest.mark.unit
def test_paired_public_release_rejects_missing_or_mismatched_frontend() -> None:
    for frontend in (None, ComposeIdentity("0.6.2", REGISTRY_DIGEST)):
        with pytest.raises(
            AlignmentError, match="backend and frontend Compose versions"
        ):
            check_alignment(
                project_version="0.6.1",
                compose=ComposeIdentity("0.6.1", REGISTRY_DIGEST),
                frontend=frontend,
                event_name="schedule",
                transport=_paired_transport(),
            )


@pytest.mark.unit
@pytest.mark.parametrize("event_name", ["pull_request", "merge_group", "push"])
def test_accepts_only_exact_pending_release_transition(event_name: str) -> None:
    state = check_alignment(
        project_version="0.5.0",
        compose=ComposeIdentity("0.4.0", REGISTRY_DIGEST),
        event_name=event_name,
        transport=_public_transport(),
        base=BaseIdentity("0.4.0", SOURCE_SHA),
    )

    assert state == "pending"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event_name", "base_version", "message"),
    [
        ("schedule", None, "fully published"),
        ("workflow_dispatch", None, "fully published"),
        ("release", None, "fully published"),
        ("pull_request", "0.3.5", "exact pending"),
        ("pull_request", "0.5.0", "exact pending"),
    ],
)
def test_rejects_non_pending_drift(
    event_name: str, base_version: str | None, message: str
) -> None:
    with pytest.raises(AlignmentError, match=message):
        check_alignment(
            project_version="0.5.0",
            compose=ComposeIdentity("0.4.0", REGISTRY_DIGEST),
            event_name=event_name,
            transport=_public_transport(),
            base=(BaseIdentity(base_version, SOURCE_SHA) if base_version else None),
        )


@pytest.mark.unit
def test_future_unchanged_revision_cannot_reuse_pending_exception() -> None:
    with pytest.raises(AlignmentError, match="exact pending"):
        check_alignment(
            project_version="0.5.0",
            compose=ComposeIdentity("0.4.0", REGISTRY_DIGEST),
            event_name="pull_request",
            transport=_public_transport(),
            base=BaseIdentity("0.5.0", SOURCE_SHA),
        )


@pytest.mark.unit
@pytest.mark.parametrize("event_name", ["pull_request", "merge_group", "push"])
def test_accepts_same_version_attempt_retry_of_unpublished_release(
    event_name: str,
) -> None:
    state = check_alignment(
        project_version="0.5.0",
        compose=ComposeIdentity("0.4.0", REGISTRY_DIGEST),
        event_name=event_name,
        transport=_public_transport(),
        base=BaseIdentity("0.5.0", SOURCE_SHA, attempt_retry=True),
    )

    assert state == "pending"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("project_version", "compose_version", "base_version"),
    [("0.5.0", "0.4.0", "0.4.1"), ("0.3.0", "0.4.0", "0.3.0")],
)
def test_attempt_retry_is_limited_to_the_unpublished_project_version(
    project_version: str, compose_version: str, base_version: str
) -> None:
    with pytest.raises(AlignmentError, match="exact pending"):
        check_alignment(
            project_version=project_version,
            compose=ComposeIdentity(compose_version, REGISTRY_DIGEST),
            event_name="pull_request",
            transport=_public_transport(),
            base=BaseIdentity(base_version, SOURCE_SHA, attempt_retry=True),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("head_attempt", "output"),
    [(2, "alignment: pending"), (3, "release attempt must increase by exactly 1")],
)
def test_main_derives_attempt_retry_from_the_exact_base_and_head(
    tmp_path: Path, mocker, capsys, head_attempt: int, output: str
) -> None:
    expected = 0 if head_attempt == 2 else 1
    head = f'[project]\nversion = "0.5.0"\n[tool.markweave.release]\nattempt = {head_attempt}\n'
    (tmp_path / "pyproject.toml").write_text(head, encoding="utf-8")
    compose = (
        f"services:\n  markweave:\n    image: {public_alignment.IMAGE_REPOSITORY}:0.4.0@{REGISTRY_DIGEST}\n"
    ).encode()
    (tmp_path / "compose.yaml").write_bytes(compose)
    mocker.patch(
        "scripts.release.public_alignment._git_output",
        side_effect=[
            f"{SOURCE_SHA} {'c' * 40}\n".encode(),
            compose,
            b'[project]\nversion = "0.5.0"\n',
            head.encode(),
        ],
    )
    mocker.patch(
        "scripts.release.public_alignment.UrlLibTransport",
        return_value=_public_transport(),
    )

    result = public_alignment.main(
        [
            "--repository",
            str(tmp_path),
            "--event-name",
            "pull_request",
            "--base",
            SOURCE_SHA,
            "--head",
            "e" * 40,
        ]
    )

    assert result == expected
    captured = capsys.readouterr()
    assert output in (captured.out if expected == 0 else captured.err)


@pytest.mark.unit
def test_rejects_pypi_compose_drift_before_trusting_other_surfaces() -> None:
    transport = _public_transport(version="0.5.0")

    with pytest.raises(AlignmentError, match="PyPI version and Compose"):
        check_alignment(
            project_version="0.5.0",
            compose=ComposeIdentity("0.4.0", REGISTRY_DIGEST),
            event_name="pull_request",
            transport=transport,
            base=BaseIdentity("0.4.0", SOURCE_SHA),
        )


def _paired_inputs(backend: str, frontend: str) -> dict[str, bytes]:
    project = b'[project]\nversion = "0.8.1"\n'
    compose = (
        f"services:\n  markweave:\n    image: {backend}\n"
        "  frontend:\n"
        f'    image: "${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{frontend}}}"\n'
        "  router:\n"
        f'    image: "${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{frontend}}}"\n'
    ).encode()
    quickstart = (
        f'readonly cutover_backend_image="${{MARKWEAVE_CUTOVER_BACKEND_IMAGE:-{backend}}}"\n'
        f'readonly cutover_frontend_image="${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{frontend}}}"\n'
    ).encode()
    return {
        "pyproject.toml": project,
        "compose.yaml": compose,
        "scripts/quickstart.sh": quickstart,
        "scripts/quickstart-simple.sh": quickstart,
    }


def _changed_inputs(
    change: str, previous: dict[str, bytes], backend: str, frontend: str
) -> dict[str, bytes]:
    compose = previous["compose.yaml"]
    project = previous["pyproject.toml"]
    quickstart = previous["scripts/quickstart.sh"]
    current = previous.copy()
    other_digest = f"sha256:{'b' * 64}".encode()
    match change:
        case "unrelated":
            current["pyproject.toml"] += b'description = "updated"\n'
            current["compose.yaml"] += b"# deployment configuration\n"
            current["scripts/quickstart.sh"] = b"# helper change \\\n" + quickstart
        case "release-attempt":
            current["pyproject.toml"] += b"[tool.markweave.release]\nattempt = 2\n"
        case "backend-pin":
            new_backend = backend.replace(":0.8.1@", ":0.8.2@").encode()
            for path in ("compose.yaml", *public_alignment.QUICKSTARTS):
                current[path] = current[path].replace(backend.encode(), new_backend)
        case "frontend-pin":
            new_frontend = frontend.encode().replace(
                REGISTRY_DIGEST.encode(), other_digest
            )
            for path in ("compose.yaml", *public_alignment.QUICKSTARTS):
                current[path] = current[path].replace(frontend.encode(), new_frontend)
        case "quickstart-pin":
            current["scripts/quickstart.sh"] = quickstart.replace(
                REGISTRY_DIGEST.encode(), other_digest
            ).replace(b'="', b'=\\\n"', 1)
        case "simple-pin":
            current["scripts/quickstart-simple.sh"] = b""
        case "quickstart-repair":
            previous["scripts/quickstart.sh"] = quickstart.replace(
                REGISTRY_DIGEST.encode(), other_digest
            )
        case "quickstart-continuation" | "quickstart-continuation-before-pin":
            current["scripts/quickstart.sh"] = {
                "quickstart-continuation": quickstart.replace(b"@", b"@\\\n", 1),
                "quickstart-continuation-before-pin": b": \\\n" + quickstart,
            }[change]
        case "adoption":
            previous["compose.yaml"] = compose.replace(b":0.8.1@", b":0.8.0@")
        case "awaiting-adoption":
            previous["pyproject.toml"] = current["pyproject.toml"] = project.replace(
                b"0.8.1", b"0.8.2"
            )
    return current


@pytest.mark.unit
@pytest.mark.parametrize(
    "scenario",
    [
        ("pull_request", "unrelated", "skipped", False),
        ("merge_group", "unrelated", "skipped", False),
        ("pull_request", "release-attempt", "aligned", True),
        (
            "pull_request",
            "backend-pin",
            "PyPI version and Compose image tag differ",
            True,
        ),
        ("pull_request", "frontend-pin", "does not match", True),
        (
            "pull_request",
            "quickstart-pin",
            "do not match the public Compose pair",
            False,
        ),
        ("pull_request", "simple-pin", "do not match the public Compose pair", False),
        ("pull_request", "quickstart-repair", "aligned", True),
        (
            "pull_request",
            "quickstart-continuation",
            "do not match the public Compose pair",
            False,
        ),
        (
            "pull_request",
            "quickstart-continuation-before-pin",
            "do not match the public Compose pair",
            False,
        ),
        (
            "pull_request",
            "dirty-compose",
            "does not match the checked-out source",
            False,
        ),
        (
            "pull_request",
            "dirty-quickstart",
            "does not match the checked-out source",
            False,
        ),
        ("pull_request", "adoption", "aligned", True),
        ("pull_request", "awaiting-adoption", "adopt published images", False),
        ("push", "unrelated", "aligned", True),
        ("release", "unrelated", "aligned", True),
        ("schedule", "unrelated", "aligned", True),
        ("workflow_dispatch", "unrelated", "aligned", True),
    ],
)
def test_cli_contacts_public_services_only_when_required(
    tmp_path: Path,
    mocker,
    capsys,
    scenario: tuple[str, str, str, bool],
) -> None:
    event, change, expected, contact_public = scenario
    backend = f"{public_alignment.IMAGE_REPOSITORY}:0.8.1@{REGISTRY_DIGEST}"
    frontend = f"{public_alignment.FRONTEND_IMAGE_REPOSITORY}:0.8.1@{REGISTRY_DIGEST}"
    previous = _paired_inputs(backend, frontend)
    current = _changed_inputs(change, previous, backend, frontend)
    (tmp_path / "scripts").mkdir()
    for path, contents in current.items():
        checkout = contents
        if change == f"dirty-{Path(path).stem}":
            checkout += b"# uncommitted"
        (tmp_path / path).write_bytes(checkout)
    base_sha = "a" * 40
    head_sha = "b" * 40

    def git_show(args: tuple[str, ...]) -> bytes:
        if args[-2] == "--format=%P":
            assert args[-1] == head_sha
            return f"{base_sha} {'c' * 40}\n".encode()
        sha, path = args[-1].split(":", maxsplit=1)
        assert sha in {base_sha, head_sha}
        return (previous if sha == base_sha else current)[path]

    mocker.patch.object(public_alignment, "_git_output", side_effect=git_show)
    transport = _paired_transport(version="0.8.1")
    client = mocker.patch.object(
        public_alignment, "UrlLibTransport", return_value=transport
    )

    result = public_alignment.main(
        [
            "--repository",
            str(tmp_path),
            "--event-name",
            event,
            "--base",
            ("f" * 40 if event == "pull_request" else base_sha),
            "--head",
            head_sha,
        ]
    )

    assert result == (0 if expected in {"aligned", "skipped"} else 1)
    captured = capsys.readouterr()
    assert expected in (captured.err if result else captured.out)
    assert bool(transport.requests) is contact_public
    assert client.called is contact_public


@pytest.mark.unit
@pytest.mark.parametrize(
    ("surface", "message"),
    [
        ("receipt", "receipt does not match"),
        ("tag", "tag does not match"),
        ("manifest", "manifest bytes"),
    ],
)
def test_rejects_public_identity_mismatches(surface: str, message: str) -> None:
    transport = _public_transport()
    if surface == "receipt":
        receipt_url = (
            f"{public_alignment.GITHUB_RELEASES}/v0.4.0/registry-publication.json"
        )
        transport.responses[receipt_url] = _json_response(
            {
                "oci_archive_manifest_digest": f"sha256:{'b' * 64}",
                "registry_manifest_digest": f"sha256:{'c' * 64}",
                "source_sha": SOURCE_SHA,
                "version": "0.4.0",
            }
        )
    elif surface == "tag":
        transport.responses[f"{public_alignment.GITHUB_API}/git/ref/tags/v0.4.0"] = (
            _json_response({"object": {"type": "commit", "sha": "d" * 40}})
        )
    else:
        manifest_url = (
            f"https://ghcr.io/v2/{public_alignment.REGISTRY_PATH}/manifests/0.4.0"
        )
        transport.responses[manifest_url] = HttpResponse(
            200,
            {"docker-content-digest": REGISTRY_DIGEST},
            b'{"schemaVersion":2}',
        )

    with pytest.raises(AlignmentError, match=message):
        check_alignment(
            project_version="0.4.0",
            compose=ComposeIdentity("0.4.0", REGISTRY_DIGEST),
            event_name="push",
            transport=transport,
        )


@pytest.mark.unit
def test_parsers_require_canonical_version_and_exact_immutable_compose_ref() -> None:
    project = b'[project]\nversion = "0.5.0"\n'
    compose = f"services:\n  markweave:\n    image: {public_alignment.IMAGE_REPOSITORY}:0.5.0@{REGISTRY_DIGEST}\n"

    assert parse_project_version(project) == "0.5.0"
    assert parse_compose_identity(compose) == ComposeIdentity("0.5.0", REGISTRY_DIGEST)

    with pytest.raises(AlignmentError, match="canonical final"):
        parse_project_version(b'[project]\nversion = "0.5.0rc1"\n')
    with pytest.raises(AlignmentError, match="immutable"):
        parse_compose_identity(
            "services:\n  markweave:\n    image: ghcr.io/example/markweave:0.5.0\n"
        )


@pytest.mark.unit
def test_compose_parser_reads_only_the_exact_backend_override_default() -> None:
    image = f"{public_alignment.IMAGE_REPOSITORY}:0.7.3@{REGISTRY_DIGEST}"
    compose = (
        "services:\n  markweave:\n"
        f'    image: "${{MARKWEAVE_CUTOVER_BACKEND_IMAGE:-{image}}}"\n'
    )

    assert parse_compose_identity(compose) == ComposeIdentity("0.7.3", REGISTRY_DIGEST)
    for rejected in (
        compose.replace("MARKWEAVE_CUTOVER_BACKEND_IMAGE", "OTHER_IMAGE"),
        compose.replace(":-", ":?"),
        compose.replace("md-converter:", "other:"),
        compose.replace(f"@{REGISTRY_DIGEST}", ""),
    ):
        with pytest.raises(AlignmentError, match="immutable"):
            parse_compose_identity(rejected)


@pytest.mark.unit
def test_repository_compose_pins_one_aligned_public_pair() -> None:
    """The release alignment reads both published images from compose.yaml."""
    document = (Path(__file__).resolve().parents[2] / "compose.yaml").read_text(
        encoding="utf-8"
    )

    backend = parse_compose_identity(document)
    frontend = parse_frontend_compose_identity(document)

    assert backend.version == frontend.version


@pytest.mark.unit
def test_frontend_compose_parser_requires_one_exact_shared_public_default() -> None:
    image = "ghcr.io/guillaume-lombardo/md-converter-web:0.6.1@sha256:" + "d" * 64
    overlay = (
        "services:\n"
        f'  frontend:\n    image: "${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{image}}}"\n'
        f'  router:\n    image: "${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{image}}}"\n'
    )

    assert parse_frontend_compose_identity(overlay) == ComposeIdentity(
        "0.6.1", f"sha256:{'d' * 64}"
    )
    with pytest.raises(AlignmentError, match="share one trusted immutable"):
        parse_frontend_compose_identity(overlay.replace("md-converter-web", "other", 1))

    unrelated = (
        "services:\n"
        f'  decoy:\n    image: "${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{image}}}"\n'
        + overlay
    )
    assert parse_frontend_compose_identity(unrelated) == ComposeIdentity(
        "0.6.1", f"sha256:{'d' * 64}"
    )
    divergent = overlay.replace(image, image.replace("d" * 64, "e" * 64), 1)
    with pytest.raises(AlignmentError, match="share one trusted immutable"):
        parse_frontend_compose_identity(divergent)


@pytest.mark.unit
@pytest.mark.parametrize("invalid_image", ["[]", "{}"])
def test_frontend_compose_parser_rejects_non_string_named_images(
    invalid_image: str,
) -> None:
    overlay = (
        "services:\n"
        f"  frontend:\n    image: {invalid_image}\n"
        f"  router:\n    image: {invalid_image}\n"
    )

    with pytest.raises(AlignmentError, match="share one trusted immutable"):
        parse_frontend_compose_identity(overlay)


@pytest.mark.unit
def test_main_reads_exact_base_and_head_only_for_pending_transition(
    tmp_path: Path, mocker, capsys
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "0.5.0"\n', encoding="utf-8"
    )
    compose = (
        f"services:\n  markweave:\n    image: {public_alignment.IMAGE_REPOSITORY}:0.4.0@{REGISTRY_DIGEST}\n"
    ).encode()
    (tmp_path / "compose.yaml").write_bytes(compose)
    inspected = mocker.patch(
        "scripts.release.public_alignment._git_output",
        side_effect=[
            f"{'f' * 40} {'c' * 40}\n".encode(),
            compose,
            b'[project]\nversion = "0.4.0"\n',
            b'[project]\nversion = "0.5.0"\n',
        ],
    )
    mocker.patch(
        "scripts.release.public_alignment.UrlLibTransport",
        return_value=_public_transport(),
    )

    result = public_alignment.main(
        [
            "--repository",
            str(tmp_path),
            "--event-name",
            "pull_request",
            "--base",
            "f" * 40,
            "--head",
            "e" * 40,
        ]
    )

    assert result == 0
    assert "alignment: pending" in capsys.readouterr().out
    assert inspected.call_args_list == [
        mocker.call(("-C", str(tmp_path), "show", "-s", "--format=%P", "e" * 40)),
        mocker.call(("-C", str(tmp_path), "show", f"{'e' * 40}:compose.yaml")),
        mocker.call(("-C", str(tmp_path), "show", f"{'f' * 40}:pyproject.toml")),
        mocker.call(("-C", str(tmp_path), "show", f"{'e' * 40}:pyproject.toml")),
    ]


@pytest.mark.unit
def test_http_redirects_are_limited_to_the_fixed_github_release_cdn() -> None:
    handler = public_alignment._TrustedRedirect()
    request = urllib.request.Request("https://github.com/release/receipt")

    redirected = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://release-assets.githubusercontent.com/release/receipt?signature=value",
    )

    assert redirected.full_url.startswith(
        "https://release-assets.githubusercontent.com/release/receipt"
    )
    with pytest.raises(AlignmentError, match="untrusted redirect"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://example.invalid/receipt",
        )


class _UrlLibResponse:
    status = 200

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def __enter__(self) -> _UrlLibResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return b"{}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "failure",
    (
        urllib.error.HTTPError(
            "https://example.test", 504, "Gateway Timeout", Message(), io.BytesIO()
        ),
        urllib.error.HTTPError(
            "https://example.test", 429, "Too Many Requests", Message(), io.BytesIO()
        ),
        urllib.error.URLError(TimeoutError("timed out")),
        urllib.error.URLError(ConnectionResetError("connection reset by peer")),
    ),
)
def test_url_lib_transport_retries_only_transient_http_or_network_failures(
    mocker, failure: urllib.error.HTTPError | urllib.error.URLError
) -> None:
    transport = public_alignment.UrlLibTransport()
    opener = mocker.Mock()
    opener.open.side_effect = [failure, _UrlLibResponse()]
    transport._opener = opener
    pause = mocker.patch("scripts.release.public_alignment.sleep")

    response = transport.request("https://example.test", headers={})

    assert response.status == 200
    assert opener.open.call_count == 2
    pause.assert_called_once_with(public_alignment.HTTP_RETRY_DELAY_SECONDS)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "expected"),
    (
        (f"{public_alignment.GITHUB_API}/releases/tags/v1.0.0", "Bearer job-token"),
        (public_alignment.PYPI_URL, None),
        ("https://github.com/owner/repo/releases/download/v1/a.json", None),
    ),
)
def test_url_lib_transport_authenticates_only_github_api_requests(
    mocker, url: str, expected: str | None
) -> None:
    transport = public_alignment.UrlLibTransport(github_token="job-token")  # noqa: S106 - test value
    opener = mocker.Mock()
    opener.open.return_value = _UrlLibResponse()
    transport._opener = opener

    transport.request(url, headers={"Accept": "application/json"})

    (request,), _ = opener.open.call_args
    assert request.get_header("Authorization") == expected


@pytest.mark.unit
@pytest.mark.parametrize("status", (401, 404))
def test_url_lib_transport_does_not_retry_auth_or_not_found_response(
    mocker, status: int
) -> None:
    transport = public_alignment.UrlLibTransport()
    opener = mocker.Mock()
    opener.open.side_effect = urllib.error.HTTPError(
        "https://example.test", status, "Permanent failure", Message(), io.BytesIO()
    )
    transport._opener = opener
    pause = mocker.patch("scripts.release.public_alignment.sleep")

    response = transport.request("https://example.test", headers={})

    assert response.status == status
    opener.open.assert_called_once()
    pause.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("failures", "message"),
    (
        (
            [urllib.error.URLError(TimeoutError("timed out")) for _ in range(3)],
            "public endpoint request failed",
        ),
        (
            [
                urllib.error.HTTPError(
                    "https://example.test",
                    504,
                    "Gateway Timeout",
                    Message(),
                    io.BytesIO(),
                )
                for _ in range(3)
            ],
            "public endpoint returned an invalid response",
        ),
    ),
)
def test_url_lib_transport_fails_closed_after_bounded_transient_retries(
    mocker, failures: list[urllib.error.HTTPError | urllib.error.URLError], message: str
) -> None:
    transport = public_alignment.UrlLibTransport()
    opener = mocker.Mock()
    opener.open.side_effect = failures
    transport._opener = opener
    pause = mocker.patch("scripts.release.public_alignment.sleep")

    with pytest.raises(AlignmentError, match=message):
        public_alignment._json_response(transport, "https://example.test")

    assert opener.open.call_count == 3
    assert pause.call_count == 2


@pytest.mark.unit
def test_url_lib_transport_does_not_retry_tls_certificate_failures(mocker) -> None:
    transport = public_alignment.UrlLibTransport()
    opener = mocker.Mock()
    opener.open.side_effect = urllib.error.URLError(
        ssl.SSLCertVerificationError("certificate verify failed")
    )
    transport._opener = opener
    pause = mocker.patch("scripts.release.public_alignment.sleep")

    with pytest.raises(AlignmentError, match="public endpoint request failed"):
        transport.request("https://example.test", headers={})

    opener.open.assert_called_once()
    pause.assert_not_called()
