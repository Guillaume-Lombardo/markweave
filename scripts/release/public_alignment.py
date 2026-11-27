"""Fail closed when package and public container release identities drift."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Any, Protocol

import yaml
from packaging.version import InvalidVersion, Version

from scripts.release.detect_version import ReleaseVersionError, detect_transition

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

PROJECT = "markweave"
REPOSITORY = "Guillaume-Lombardo/markweave"
IMAGE_REPOSITORY = "ghcr.io/guillaume-lombardo/md-converter"
FRONTEND_IMAGE_REPOSITORY = "ghcr.io/guillaume-lombardo/md-converter-web"
REGISTRY_PATH = "guillaume-lombardo/md-converter"
FRONTEND_REGISTRY_PATH = "guillaume-lombardo/md-converter-web"
REVERSE_REGISTRY_PATH = "guillaume-lombardo/md-converter-reverse-attempt"
PYPI_URL = f"https://pypi.org/pypi/{PROJECT}/json"
GITHUB_API = f"https://api.github.com/repos/{REPOSITORY}"
GITHUB_RELEASES = f"https://github.com/{REPOSITORY}/releases/download"
GHCR_TOKEN_URL = (
    f"https://ghcr.io/token?service=ghcr.io&scope=repository:{REGISTRY_PATH}:pull"
)
CANDIDATE_EVENTS = frozenset({"pull_request", "merge_group"})
PENDING_EVENTS = CANDIDATE_EVENTS | {"push"}
KNOWN_EVENTS = PENDING_EVENTS | frozenset({"release", "workflow_dispatch", "schedule"})
FULL_SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
IMAGE = re.compile(
    rf"{re.escape(IMAGE_REPOSITORY)}:(?P<tag>[0-9A-Za-z][0-9A-Za-z._-]*)"
    r"@(?P<digest>sha256:[0-9a-f]{64})"
)
FRONTEND_IMAGE = re.compile(
    rf"{re.escape(FRONTEND_IMAGE_REPOSITORY)}:(?P<tag>[0-9A-Za-z][0-9A-Za-z._-]*)"
    r"@(?P<digest>sha256:[0-9a-f]{64})"
)
BACKEND_IMAGE_DEFAULT = re.compile(
    r"\$\{MARKWEAVE_CUTOVER_BACKEND_IMAGE:-(?P<image>[^}]+)\}"
)
FRONTEND_IMAGE_DEFAULT = re.compile(
    r"\$\{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-(?P<image>[^}]+)\}"
)
PAIRED_RELEASE_FIRST_VERSION = Version("0.6.1")
ZERO_SHA = "0" * 40
PULL_REQUEST_MERGE_PARENTS = 2
MAX_JSON_BYTES = 1_048_576
MAX_RECEIPT_BYTES = 16_384
MAX_TOKEN_BYTES = 16_384
HTTP_TIMEOUT_SECONDS = 10.0
HTTP_RETRY_ATTEMPTS = 3
HTTP_RETRY_DELAY_SECONDS = 1.0
HTTP_OK = 200
TRANSIENT_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
OCI_SCHEMA_VERSION = 2
CUTOVER_FRONTEND_ROLES = ("frontend", "router")
QUICKSTARTS = ("scripts/quickstart.sh", "scripts/quickstart-simple.sh")
QUICKSTART_PIN = re.compile(
    r'(?m)^[ \t]*readonly[ \t]+cutover_(backend|frontend)_image="([^"\n]+)"'
    r"(?:[ \t]+#[^\n]*)?[ \t]*$"
)


class AlignmentError(ValueError):
    """The repository and public release surfaces are not safely aligned."""


@dataclass(frozen=True)
class HttpResponse:
    """One bounded HTTP response used by the injectable public client."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    """Minimal network boundary for deterministic tests."""

    def request(self, url: str, *, headers: Mapping[str, str]) -> HttpResponse:
        """Return one response without following redirects."""


class _TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(  # noqa: PLR0913, PLR0917 - required stdlib override
        self, req, fp, code, msg, headers, newurl
    ):
        origin = urllib.parse.urlsplit(req.full_url)
        target = urllib.parse.urlsplit(newurl)
        if (origin.scheme, origin.hostname) != ("https", "github.com") or (
            target.scheme,
            target.hostname,
        ) != ("https", "release-assets.githubusercontent.com"):
            raise AlignmentError("public endpoint returned an untrusted redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrlLibTransport:
    """Bounded HTTPS-only transport for the fixed public endpoints."""

    def __init__(
        self, *, maximum_bytes: int = MAX_JSON_BYTES, github_token: str | None = None
    ) -> None:
        self._maximum_bytes = maximum_bytes
        # Hosted runners share egress addresses, so anonymous GitHub API calls hit
        # the shared rate limit intermittently. Only api.github.com gets the token.
        self._github_token = github_token
        self._opener = urllib.request.build_opener(_TrustedRedirect)

    def request(self, url: str, *, headers: Mapping[str, str]) -> HttpResponse:
        for attempt in range(HTTP_RETRY_ATTEMPTS):
            try:
                response = self._request_once(url, headers=headers)
            except (OSError, urllib.error.URLError) as error:
                if (
                    self._is_transient_network_error(error)
                    and attempt + 1 < HTTP_RETRY_ATTEMPTS
                ):
                    sleep(HTTP_RETRY_DELAY_SECONDS)
                    continue
                raise AlignmentError(
                    f"public endpoint request failed: {url}"
                ) from error
            if (
                response.status in TRANSIENT_HTTP_STATUSES
                and attempt + 1 < HTTP_RETRY_ATTEMPTS
            ):
                sleep(HTTP_RETRY_DELAY_SECONDS)
                continue
            return response
        raise AssertionError("bounded public endpoint retry loop did not return")

    @staticmethod
    def _is_transient_network_error(error: OSError | urllib.error.URLError) -> bool:
        return isinstance(error, (TimeoutError, ConnectionResetError)) or (
            isinstance(error, urllib.error.URLError)
            and isinstance(error.reason, (TimeoutError, ConnectionResetError))
        )

    def _request_once(self, url: str, *, headers: Mapping[str, str]) -> HttpResponse:
        if not url.startswith("https://"):
            raise AlignmentError("public release checks require HTTPS")
        request_headers = dict(headers)
        if (
            self._github_token is not None
            and urllib.parse.urlsplit(url).hostname == "api.github.com"
            and "Authorization" not in request_headers
        ):
            request_headers["Authorization"] = f"Bearer {self._github_token}"
        request = urllib.request.Request(  # noqa: S310 - HTTPS checked above
            url, headers=request_headers
        )
        try:
            with self._opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                body = response.read(self._maximum_bytes + 1)
                if len(body) > self._maximum_bytes:
                    raise AlignmentError(
                        "public endpoint response exceeds the size limit"
                    )
                return HttpResponse(
                    status=response.status,
                    headers={
                        key.lower(): value for key, value in response.headers.items()
                    },
                    body=body,
                )
        except urllib.error.HTTPError as error:
            try:
                body = error.read(self._maximum_bytes + 1)
            finally:
                error.close()
            if len(body) > self._maximum_bytes:
                raise AlignmentError(
                    "public endpoint response exceeds the size limit"
                ) from error
            return HttpResponse(
                status=error.code,
                headers={
                    key.lower(): value for key, value in (error.headers or {}).items()
                },
                body=body,
            )


@dataclass(frozen=True)
class ComposeIdentity:
    """The exact public image selected by Compose."""

    version: str
    digest: str


@dataclass(frozen=True)
class BaseIdentity:
    """The exact repository base for one pending release transition."""

    version: str
    source_sha: str
    attempt_retry: bool = False


def _canonical_final_version(value: object, *, label: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise AlignmentError(f"{label} must be a canonical final version string")
    try:
        parsed = Version(value)
    except InvalidVersion as error:
        raise AlignmentError(f"{label} is not valid PEP 440") from error
    if (
        value != str(parsed)
        or parsed.is_prerelease
        or parsed.is_devrelease
        or parsed.local is not None
        or parsed.epoch != 0
    ):
        raise AlignmentError(f"{label} must be a canonical final public version")
    return value


def parse_project_version(document: bytes, *, label: str = "pyproject.toml") -> str:
    """Parse the authoritative project version from one bounded TOML document."""
    try:
        value = tomllib.loads(document.decode("utf-8"))["project"]["version"]
    except (UnicodeDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as error:
        raise AlignmentError(f"{label} has no valid project.version") from error
    return _canonical_final_version(value, label=f"{label} project.version")


def parse_compose_identity(document: str) -> ComposeIdentity:
    """Parse only the public image of the exact Compose markweave service.

    The image is either the literal public reference or the public default of the
    exact ``MARKWEAVE_CUTOVER_BACKEND_IMAGE`` interpolation used by quickstarts.
    """
    try:
        compose = yaml.safe_load(document)
        image = compose["services"]["markweave"]["image"]
    except (yaml.YAMLError, KeyError, TypeError) as error:
        raise AlignmentError(
            "compose.yaml has no valid services.markweave.image"
        ) from error
    if isinstance(image, str) and (default := BACKEND_IMAGE_DEFAULT.fullmatch(image)):
        image = default.group("image")
    if not isinstance(image, str) or (match := IMAGE.fullmatch(image)) is None:
        raise AlignmentError(
            "Compose markweave image must use the trusted repository, a version tag, "
            "and an immutable sha256 digest"
        )
    version = _canonical_final_version(match.group("tag"), label="Compose image tag")
    return ComposeIdentity(version=version, digest=match.group("digest"))


def parse_frontend_compose_identity(document: str) -> ComposeIdentity:
    """Parse the shared published frontend default from compose.yaml."""
    try:
        compose = yaml.load(document, Loader=yaml.BaseLoader)  # noqa: S506
        services = compose["services"]
        configured = [services[role]["image"] for role in CUTOVER_FRONTEND_ROLES]
    except (yaml.YAMLError, KeyError, TypeError) as error:
        raise AlignmentError(
            "compose.yaml has no valid frontend and router image defaults"
        ) from error
    if any(not isinstance(image, str) for image in configured):
        raise AlignmentError(
            "cutover frontend services must share one trusted immutable public default"
        )
    matches = [FRONTEND_IMAGE_DEFAULT.fullmatch(image) for image in configured]
    images = [match.group("image") for match in matches if match is not None]
    if (
        len(images) != len(CUTOVER_FRONTEND_ROLES)
        or images[0] != images[1]
        or (match := FRONTEND_IMAGE.fullmatch(images[0])) is None
    ):
        raise AlignmentError(
            "cutover frontend services must share one trusted immutable public default"
        )
    version = _canonical_final_version(
        match.group("tag"), label="frontend Compose image tag"
    )
    return ComposeIdentity(version=version, digest=match.group("digest"))


def _json_response(
    transport: Transport,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    maximum_bytes: int = MAX_JSON_BYTES,
) -> dict[str, Any]:
    response = transport.request(
        url,
        headers={"Accept": "application/json", **(headers or {})},
    )
    return _json_object(response, url, maximum_bytes=maximum_bytes)


def _json_object(
    response: HttpResponse, url: str, *, maximum_bytes: int
) -> dict[str, Any]:
    if response.status != HTTP_OK or len(response.body) > maximum_bytes:
        raise AlignmentError(f"public endpoint returned an invalid response: {url}")
    try:
        value = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlignmentError(f"public endpoint returned invalid JSON: {url}") from error
    if not isinstance(value, dict):
        raise AlignmentError(f"public endpoint JSON must be an object: {url}")
    return value


def _pypi_version(transport: Transport) -> str:
    document = _json_response(transport, PYPI_URL)
    info = document.get("info")
    if not isinstance(info, dict):
        raise AlignmentError("PyPI response has no info object")
    return _canonical_final_version(info.get("version"), label="latest PyPI version")


def _release_identity(transport: Transport, *, version: str) -> tuple[str, list[Any]]:
    tag = f"v{version}"
    release_url = f"{GITHUB_API}/releases/tags/{tag}"
    release = _json_response(transport, release_url)
    source_sha = release.get("target_commitish")
    if (
        release.get("tag_name") != tag
        or not isinstance(source_sha, str)
        or FULL_SHA.fullmatch(source_sha) is None
        or release.get("draft") is not False
        or release.get("prerelease") is not False
        or not isinstance(release.get("published_at"), str)
    ):
        raise AlignmentError(
            "GitHub Release identity does not match the public version"
        )

    ref = _json_response(transport, f"{GITHUB_API}/git/ref/tags/{tag}")
    ref_object = ref.get("object")
    if not isinstance(ref_object, dict) or (
        ref_object.get("type"),
        ref_object.get("sha"),
    ) != ("commit", source_sha):
        raise AlignmentError("GitHub tag does not match the published Release source")

    assets = release.get("assets")
    if not isinstance(assets, list):
        raise AlignmentError("GitHub Release assets are invalid")
    return source_sha, assets


def _release_asset(
    transport: Transport,
    *,
    version: str,
    assets: list[Any],
    name: str,
    maximum_bytes: int,
) -> tuple[dict[str, Any], bytes]:
    url = f"{GITHUB_RELEASES}/v{version}/{name}"
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("name") == name
    ]
    if len(matches) != 1 or matches[0].get("browser_download_url") != url:
        raise AlignmentError(f"GitHub Release has no unique trusted {name} asset")
    response = transport.request(url, headers={"Accept": "application/json"})
    return _json_object(response, url, maximum_bytes=maximum_bytes), response.body


def _receipt_digest(
    receipt: Mapping[str, Any], *, source_sha: str, version: str
) -> str:
    archive_digest = receipt.get("oci_archive_manifest_digest")
    registry_digest = receipt.get("registry_manifest_digest")
    if (
        set(receipt)
        != {
            "oci_archive_manifest_digest",
            "registry_manifest_digest",
            "source_sha",
            "version",
        }
        or not isinstance(archive_digest, str)
        or DIGEST.fullmatch(archive_digest) is None
        or not isinstance(registry_digest, str)
        or DIGEST.fullmatch(registry_digest) is None
    ):
        raise AlignmentError("GitHub publication receipt has an invalid shape")
    if (receipt.get("source_sha"), receipt.get("version")) != (source_sha, version):
        raise AlignmentError(
            "GitHub publication receipt does not match the public release"
        )
    return registry_digest


def _release_receipt(
    transport: Transport,
    *,
    version: str,
    expected_digest: str,
    role: str | None = None,
) -> None:
    source_sha, assets = _release_identity(transport, version=version)
    receipt_name = (
        f"{role}-registry-publication.json" if role else "registry-publication.json"
    )
    receipt, _ = _release_asset(
        transport,
        version=version,
        assets=assets,
        name=receipt_name,
        maximum_bytes=MAX_RECEIPT_BYTES,
    )
    if (
        _receipt_digest(receipt, source_sha=source_sha, version=version)
        != expected_digest
    ):
        raise AlignmentError(
            "GitHub publication receipt does not match the public release"
        )


def _ghcr_manifest_response(
    transport: Transport,
    *,
    repository_path: str,
    version: str,
) -> HttpResponse:
    token_url = (
        f"https://ghcr.io/token?service=ghcr.io&scope=repository:{repository_path}:pull"
    )
    token_response = transport.request(
        token_url, headers={"Accept": "application/json"}
    )
    token = _ghcr_pull_token(
        token_response, label="GHCR returned an invalid pull token response"
    )
    return _ghcr_manifest_with_token(
        transport, repository_path=repository_path, version=version, token=token
    )


def _ghcr_pull_token(response: HttpResponse, *, label: str) -> str:
    if response.status != HTTP_OK or len(response.body) > MAX_TOKEN_BYTES:
        raise AlignmentError(label)
    try:
        document = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlignmentError(label) from error
    if not isinstance(document, dict):
        raise AlignmentError(label)
    token = document.get("token", document.get("access_token"))
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_BYTES:
        raise AlignmentError(label)
    return token


def _ghcr_manifest_with_token(
    transport: Transport, *, repository_path: str, version: str, token: str
) -> HttpResponse:
    return transport.request(
        f"https://ghcr.io/v2/{repository_path}/manifests/{version}",
        headers={
            "Accept": (
                "application/vnd.oci.image.manifest.v1+json, "
                "application/vnd.docker.distribution.manifest.v2+json"
            ),
            "Authorization": f"Bearer {token}",
        },
    )


def _ghcr_digest(
    transport: Transport, *, version: str, repository_path: str = REGISTRY_PATH
) -> str:
    response = _ghcr_manifest_response(
        transport, repository_path=repository_path, version=version
    )
    headers = {key.lower(): value for key, value in response.headers.items()}
    digest = headers.get("docker-content-digest")
    if (
        response.status != HTTP_OK
        or not isinstance(digest, str)
        or DIGEST.fullmatch(digest) is None
    ):
        raise AlignmentError("GHCR manifest response has no immutable digest")
    if f"sha256:{hashlib.sha256(response.body).hexdigest()}" != digest:
        raise AlignmentError("GHCR manifest bytes do not match its public digest")
    try:
        manifest = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlignmentError("GHCR manifest is invalid JSON") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schemaVersion") != OCI_SCHEMA_VERSION
    ):
        raise AlignmentError("GHCR manifest has an invalid shape")
    return digest


def _git_output(arguments: Sequence[str]) -> bytes:
    try:
        return subprocess.run(  # noqa: S603 - fixed executable and bounded arguments
            ["/usr/bin/git", *arguments], check=True, capture_output=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise AlignmentError("cannot inspect the exact Git transition") from error


def _git_file(repository: Path, sha: str, path: str) -> bytes:
    return _git_output(("-C", str(repository), "show", f"{sha}:{path}"))


def _read_file(repository: Path, path: str, *, head: str = "") -> bytes:
    document = (repository / path).read_bytes()
    if head and document != _git_file(repository, head, path):
        raise AlignmentError(f"head {path} does not match the checked-out source")
    return document


def _candidate_base(repository: Path, *, event: str, base: str, head: str) -> str:
    if FULL_SHA.fullmatch(head) is None or head == ZERO_SHA:
        raise AlignmentError("candidates require a nonzero full head SHA")
    if event != "pull_request":
        return base
    # GitHub checks out the synthetic merge commit. Its first parent is the
    # base it was built against, even when the event payload names an older SHA.
    parents = _git_output(("-C", str(repository), "show", "-s", "--format=%P", head))
    parent_shas = parents.decode("ascii").split()
    if len(parent_shas) != PULL_REQUEST_MERGE_PARENTS:
        raise AlignmentError("pull request head must be a two-parent merge commit")
    return parent_shas[0]


def _base_identity(
    repository: Path, *, base: str, head: str, project: bytes
) -> BaseIdentity:
    if (
        FULL_SHA.fullmatch(base) is None
        or base == ZERO_SHA
        or FULL_SHA.fullmatch(head) is None
        or head == ZERO_SHA
    ):
        raise AlignmentError(
            "pending transitions require nonzero full base and head SHAs"
        )
    previous = _git_file(repository, base, "pyproject.toml")
    reviewed_head = _git_file(repository, head, "pyproject.toml")
    if reviewed_head != project:
        raise AlignmentError(
            "head pyproject.toml does not match the checked-out source"
        )
    base_version = parse_project_version(previous, label="base pyproject.toml")
    try:
        transition = detect_transition(previous, reviewed_head)
    except ReleaseVersionError as error:
        raise AlignmentError(str(error)) from error
    return BaseIdentity(
        version=base_version,
        source_sha=base,
        attempt_retry=transition is not None and transition.version == base_version,
    )


def _compose_images(document: str) -> tuple[ComposeIdentity, ComposeIdentity | None]:
    backend = parse_compose_identity(document)
    frontend = (
        parse_frontend_compose_identity(document)
        if Version(backend.version) >= PAIRED_RELEASE_FIRST_VERSION
        else None
    )
    return backend, frontend


def _quickstart_pins(document: bytes) -> list[tuple[str, str]]:
    # Receipt adoption replaces contiguous image references in these declarations.
    return sorted(QUICKSTART_PIN.findall(document.decode("utf-8")))


def _check_quickstart_pins(
    repository: Path, *, head: str, backend: ComposeIdentity, frontend: ComposeIdentity
) -> dict[str, list[tuple[str, str]]]:
    expected = [
        (
            "backend",
            f"${{MARKWEAVE_CUTOVER_BACKEND_IMAGE:-{IMAGE_REPOSITORY}:{backend.version}@{backend.digest}}}",
        ),
        (
            "frontend",
            f"${{MARKWEAVE_CUTOVER_FRONTEND_IMAGE:-{FRONTEND_IMAGE_REPOSITORY}:{frontend.version}@{frontend.digest}}}",
        ),
    ]
    pins = {
        path: _quickstart_pins(_read_file(repository, path, head=head))
        for path in QUICKSTARTS
    }
    for path, actual in pins.items():
        if actual != expected:
            raise AlignmentError(
                f"{path} image pins do not match the public Compose pair"
            )
    return pins


def _pin_changes(
    repository: Path,
    *,
    base: str,
    images: tuple[ComposeIdentity, ComposeIdentity | None],
    quickstarts: Mapping[str, list[tuple[str, str]]],
) -> bool:
    previous = _git_file(repository, base, "compose.yaml")
    return _compose_images(previous.decode("utf-8")) != images or any(
        _quickstart_pins(_git_file(repository, base, path)) != pins
        for path, pins in quickstarts.items()
    )


def check_alignment(  # noqa: PLR0913 - explicit release transition cases and injectable surfaces
    *,
    project_version: str,
    compose: ComposeIdentity,
    event_name: str,
    transport: Transport,
    base: BaseIdentity | None = None,
    frontend: ComposeIdentity | None = None,
) -> str:
    """Verify normal alignment or the sole exact pending-release transition."""
    if event_name not in KNOWN_EVENTS:
        raise AlignmentError(f"unsupported GitHub event: {event_name}")
    pypi_version = _pypi_version(transport)
    if pypi_version != compose.version:
        raise AlignmentError("latest PyPI version and Compose image tag differ")
    if project_version != compose.version:
        if event_name not in PENDING_EVENTS:
            raise AlignmentError("this event requires fully published alignment")
        version_transition = (
            base is not None
            and base.version == compose.version
            and Version(project_version) > Version(base.version)
        )
        # A protected same-version retry after a failed run that published nothing.
        attempt_retry = (
            base is not None
            and base.attempt_retry
            and base.version == project_version
            and Version(project_version) > Version(compose.version)
        )
        if not (version_transition or attempt_retry):
            raise AlignmentError(
                "repository state is not an exact pending version transition"
            )
        state = "pending"
    else:
        if base is not None:
            raise AlignmentError("base version is only valid for a pending transition")
        state = "aligned"
    paired_release = Version(compose.version) >= PAIRED_RELEASE_FIRST_VERSION
    if paired_release and (frontend is None or frontend.version != compose.version):
        raise AlignmentError("published backend and frontend Compose versions differ")
    _release_receipt(
        transport,
        version=compose.version,
        expected_digest=compose.digest,
        role="backend" if paired_release else None,
    )
    if _ghcr_digest(transport, version=compose.version) != compose.digest:
        raise AlignmentError("public GHCR digest and Compose digest differ")
    if paired_release and frontend is not None:
        _release_receipt(
            transport,
            version=frontend.version,
            expected_digest=frontend.digest,
            role="frontend",
        )
        if (
            _ghcr_digest(
                transport,
                version=frontend.version,
                repository_path=FRONTEND_REGISTRY_PATH,
            )
            != frontend.digest
        ):
            raise AlignmentError("public frontend GHCR and Compose digests differ")
    return state


def _arguments(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--event-name", required=True, choices=sorted(KNOWN_EVENTS))
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Check the current repository against fixed public release surfaces."""
    options = _arguments(arguments)
    try:
        candidate = options.event_name in CANDIDATE_EVENTS
        base_sha = (
            _candidate_base(
                options.repository,
                event=options.event_name,
                base=options.base,
                head=options.head,
            )
            if candidate
            else options.base
        )
        project = (options.repository / "pyproject.toml").read_bytes()
        project_version = parse_project_version(project)
        head = options.head if candidate else ""
        images = _compose_images(
            _read_file(options.repository, "compose.yaml", head=head).decode("utf-8")
        )
        compose, frontend = images
        pending = project_version != compose.version
        base = None
        if pending or candidate:
            if options.event_name not in PENDING_EVENTS:
                raise AlignmentError("this event requires fully published alignment")
            base = _base_identity(
                options.repository,
                base=base_sha,
                head=options.head,
                project=project,
            )
        quickstarts = (
            _check_quickstart_pins(
                options.repository, head=head, backend=compose, frontend=frontend
            )
            if frontend is not None
            else {}
        )
        if base is not None and candidate:
            release_changed = base.version != project_version or base.attempt_retry
            if not release_changed and not _pin_changes(
                options.repository,
                base=base.source_sha,
                images=images,
                quickstarts=quickstarts,
            ):
                if pending:
                    raise AlignmentError("adopt published images before other changes")
                print(
                    "public release alignment: skipped (no release or image pin changes)"
                )
                return 0
        state = check_alignment(
            project_version=project_version,
            compose=compose,
            event_name=options.event_name,
            transport=UrlLibTransport(
                github_token=os.environ.get("GITHUB_API_TOKEN") or None
            ),
            base=base if pending else None,
            frontend=frontend,
        )
    except (AlignmentError, OSError, UnicodeDecodeError) as error:
        print(f"public release alignment failed: {error}", file=sys.stderr)
        return 1
    print(f"public release alignment: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
