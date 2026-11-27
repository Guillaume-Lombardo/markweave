"""Exercise forward upload limits against the deployed rootless images."""

import http.client
import io
import json
import os
import zipfile
from contextlib import ExitStack
from urllib.parse import urlsplit

import pytest
from PIL import Image

from scripts.container.api_workflow_smoke import multipart
from tests.e2e.service_workflow import (
    ServiceClient,
    decode_object,
    error_payload,
    expect,
    wait_for_job,
)

pytestmark = [pytest.mark.e2e, pytest.mark.requires_podman]


def _archive() -> bytes:
    image = io.BytesIO()
    Image.new("RGB", (2_500, 1_000), "blue").save(image, format="PNG")
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("document.md", "![Photo](assets/photo.png)\n")
        archive.writestr("assets/photo.png", image.getvalue())
        archive.writestr("notes.md", b"x" * 700_000)
        archive.writestr("appendix.md", b"y" * 400_000)
    return source.getvalue()


def test_confirmed_archive_and_resized_docx() -> None:
    client = ServiceClient(os.environ["MARKWEAVE_E2E_CONVERSION_URL"])
    actor = client.login("e2e-admin", "e2e-admin-password")
    archive = _archive()

    def submit(source: bytes, *, confirmed: bool):
        fields = [("output", "docx")]
        if confirmed:
            fields.append(("allow_large_archive", "true"))
        body, content_type = multipart(fields, [("source", "sizing.zip", source)])
        return client.request(
            "POST",
            "/api/v1/conversions",
            body=body,
            content_type=content_type,
            mutate=True,
        )

    rejected = submit(archive, confirmed=False)
    expect(rejected, 413, "unconfirmed large archive")
    error = error_payload(rejected)
    assert error["code"] == "ARCHIVE_SIZE_CONFIRMATION_REQUIRED"
    assert error["dimension"] == "upload"
    assert error["actual_bytes"] == len(archive)

    above_hard = submit(b"x" * 4_000_001, confirmed=True)
    expect(above_hard, 413, "hard upload ceiling")
    assert error_payload(above_hard)["code"] == "CONVERSION_SIZE_LIMIT_EXCEEDED"

    accepted = submit(archive, confirmed=True)
    expect(accepted, 202, "confirmed large archive")
    job = decode_object(accepted, "read confirmed conversion")
    location = accepted.headers["location"]
    finished = wait_for_job(client, location)
    assert finished["state"] == "succeeded", finished.get("error_code")
    assert finished["warnings"] == [
        "Image 'assets/photo.png' resized from 2500\u00d71000 to 2000\u00d7800."
    ]
    download = client.request("GET", location + "/result")
    expect(download, 200, "download resized DOCX")
    with zipfile.ZipFile(io.BytesIO(download.body)) as docx:
        (image_name,) = (
            name for name in docx.namelist() if name.startswith("word/media/")
        )
        with Image.open(io.BytesIO(docx.read(image_name))) as embedded:
            assert embedded.format == "PNG"
            assert embedded.size == (2_000, 800)

    audit = client.request("GET", "/api/v1/audit")
    expect(audit, 200, "read large archive audit")
    assert any(
        entry["operation"] == "large_archive_override"
        and entry["target_id"] == job["id"]
        and entry["actor_id"] == actor["user"]["id"]
        and any(size["actual_bytes"] == len(archive) for size in entry["sizes"])
        for entry in json.loads(audit.body)
    )


def _assert_upload_timeout(connection: http.client.HTTPConnection) -> None:
    with connection.getresponse() as timed_out:
        assert timed_out.status == 408
        assert timed_out.getheader("Connection") == "close"
        assert json.loads(timed_out.read())["error"]["code"] == (
            "CONVERSION_UPLOAD_TIMED_OUT"
        )


def test_forward_upload_saturation_rejects_before_reading_and_allows_retry() -> None:
    base_url = os.environ["MARKWEAVE_E2E_CONVERSION_URL"]
    origin = urlsplit(base_url)
    assert origin.scheme == "http"
    host = origin.hostname
    assert host is not None
    client = ServiceClient(base_url)
    login = client.request(
        "POST",
        "/api/v1/login",
        body=b'{"username":"e2e-admin","password":"e2e-admin-password"}',
        content_type="application/json",
    )
    expect(login, 200, "sign in for concurrent forward uploads")
    cookie = next(
        raw.split(";", 1)[0]
        for raw in login.set_cookies
        if raw.startswith("md_converter_session=")
    )
    csrf = decode_object(login, "read upload session")["csrf_token"]
    body, content_type = multipart(
        [("output", "docx")], [("source", "capacity.md", b"# Upload capacity")]
    )
    path = "/api/v1/conversions"
    before = decode_object(client.request("GET", path), "list jobs before upload")
    before_audit = client.request("GET", "/api/v1/audit")
    expect(before_audit, 200, "read audit before upload")

    def start_upload(connections: ExitStack) -> http.client.HTTPConnection:
        connection = http.client.HTTPConnection(host, origin.port, timeout=20)
        connections.callback(connection.close)
        connection.putrequest("POST", path)
        connection.putheader("Cookie", cookie)
        connection.putheader("X-CSRF-Token", csrf)
        connection.putheader("Content-Type", content_type)
        connection.putheader("Content-Length", str(len(body)))
        connection.putheader("Expect", "100-continue")
        connection.endheaders()
        return connection

    with ExitStack() as connections:
        pending = [start_upload(connections) for _ in range(4)]
        for connection in pending:
            assert connection.sock is not None
            # Uvicorn acknowledges only when the application first reads the body.
            with connection.sock.makefile("rb") as stream:
                assert stream.readline().split()[:2] == [b"HTTP/1.1", b"100"]
                assert stream.readline() == b"\r\n"

        # Send no body. If the application asks for it, getresponse will time out.
        with start_upload(connections).getresponse() as rejected:
            assert rejected.status == 503
            assert rejected.getheader("Retry-After") == "1"
            assert json.loads(rejected.read())["error"]["code"] == (
                "CONVERSION_UPLOAD_CAPACITY_EXCEEDED"
            )
        assert (
            decode_object(client.request("GET", path), "list jobs at capacity")["total"]
            == before["total"]
        )
        assert client.request("GET", "/api/v1/audit").body == before_audit.body

        first = pending[0]
        first.send(body)
        with first.getresponse() as admitted:
            assert admitted.status == 202
            admitted.read()
        retried = client.request(
            "POST",
            path,
            body=body,
            content_type=content_type,
            headers={"X-CSRF-Token": csrf},
        )
        expect(retried, 202, "retry forward upload after a slot is released")
        finished = wait_for_job(client, retried.headers["location"])
        assert finished["state"] == "succeeded"

        _assert_upload_timeout(pending[1])
        assert (
            decode_object(client.request("GET", path), "list jobs after body timeout")[
                "total"
            ]
            == before["total"] + 2
        )
        expect(
            client.request(
                "POST",
                path,
                body=body,
                content_type=content_type,
                headers={"X-CSRF-Token": csrf},
            ),
            202,
            "submit on a new connection after body timeout",
        )
