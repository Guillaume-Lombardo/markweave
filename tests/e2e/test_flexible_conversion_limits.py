"""Exercise confirmation and resizing against the deployed rootless images."""

import io
import json
import os
import zipfile

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
