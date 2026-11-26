"""Real HTTP and SQLite confirmation and audit behavior."""

import io
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from markweave.app import create_app
from markweave.config import Settings
from markweave.malware import TrustingUploadScanner
from markweave.persistence.retention import SqlRetentionRepository
from markweave.persistence.sql import create_database_engine, standalone_database_url
from tests.functional.test_conversion_api import login
from tests.settings import template_settings

pytestmark = [pytest.mark.integration, pytest.mark.light_coverage]


def _source(member_bytes: int, *, compression: int) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.writestr("document.md", b"x" * member_bytes)
        archive.writestr("notes.md", b"y" * member_bytes)
    return buffer.getvalue()


@pytest.fixture
def service(tmp_path: Path):
    password = "admin-" + "password"
    settings = Settings(
        **template_settings(conversion_max_decompressed_bytes=600),
        initial_admin_username="admin",
        initial_admin_password=password,
        argon2_memory_cost=8,
        argon2_time_cost=1,
        storage_profile="standalone",
        standalone_data_directory=tmp_path,
        conversion_upload_max_bytes=380,
        conversion_upload_hard_max_bytes=1_200,
        conversion_hard_max_decompressed_bytes=1_000,
        conversion_request_max_bytes=1_024,
        conversion_retry_after_seconds=1,
        job_result_retention_seconds=3_600,
    )
    scanner = TrustingUploadScanner()
    with TestClient(
        create_app(settings, scanner=scanner), base_url="https://testserver"
    ) as client:
        actor = login(client, "admin", password)
        yield client, actor, settings


@pytest.mark.parametrize(
    ("dimension", "source", "limits"),
    [
        ("upload", _source(180, compression=zipfile.ZIP_STORED), (380, 1_200)),
        ("decompressed", _source(400, compression=zipfile.ZIP_DEFLATED), (600, 1_000)),
    ],
)
def test_confirmation_admits_once_and_writes_immutable_audit(
    service, tmp_path, dimension, source, limits
) -> None:
    client, actor, settings = service
    soft, hard = limits
    headers = {"X-CSRF-Token": actor["csrf_token"], "Idempotency-Key": "same-source"}
    options = client.get("/api/v1/conversion-options").json()
    assert options["conversion_upload_max_bytes"] == 380
    assert options["conversion_upload_hard_max_bytes"] == 1_200

    def submit(confirmed: bool):
        return client.post(
            "/api/v1/conversions",
            headers=headers,
            files={"source": ("source.zip", source)},
            data={"output": "docx", "allow_large_archive": str(confirmed).lower()},
        )

    rejected = submit(False)
    assert rejected.status_code == 413
    error = rejected.json()["error"]
    assert (
        error["code"],
        error["dimension"],
        error["soft_limit_bytes"],
        error["hard_limit_bytes"],
    ) == (
        "ARCHIVE_SIZE_CONFIRMATION_REQUIRED",
        dimension,
        soft,
        hard,
    )
    assert error["actual_bytes"] == (
        800 if dimension == "decompressed" else len(source)
    )
    assert client.get("/api/v1/conversions").json()["total"] == 0
    accepted = submit(True)
    assert accepted.status_code == 202
    job = accepted.json()
    assert submit(True).json()["id"] == job["id"]
    # A replay remains the same request after the administrator raises both
    # standard limits and the same bytes no longer require an override.
    settings.conversion_upload_max_bytes = 1_000
    settings.conversion_max_decompressed_bytes = 1_000
    replay = submit(True)
    assert replay.status_code == 202
    assert replay.json()["id"] == job["id"]
    audit = _override_audit(client)
    assert len(audit) == 1
    assert (audit[0]["operation"], audit[0]["actor_id"], audit[0]["target_id"]) == (
        "large_archive_override",
        actor["user"]["id"],
        job["id"],
    )
    assert {entry["dimension"] for entry in audit[0]["sizes"]} == {
        "upload",
        "decompressed",
    }
    assert any(
        entry["actual_bytes"] == error["actual_bytes"] for entry in audit[0]["sizes"]
    )

    engine = create_database_engine(standalone_database_url(tmp_path))
    try:
        with pytest.raises(DatabaseError), engine.begin() as connection:
            connection.execute(text("DELETE FROM conversion_size_audit"))
        with pytest.raises(DatabaseError), engine.begin() as connection:
            connection.execute(text("UPDATE conversion_size_audit SET sizes = '[]'"))
        kept_at = datetime.now(UTC)
        repository = SqlRetentionRepository(engine)
        assert (
            repository.cleanup_audits(
                cutoff_at=kept_at - timedelta(days=365),
                completed_at=kept_at,
                limit=1,
            )
            == 0
        )
        assert (
            repository.cleanup_audits(
                cutoff_at=kept_at,
                completed_at=kept_at + timedelta(days=365),
                limit=10,
            )
            == 2
        )
        assert _override_audit(client) == []
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("source", "dimension", "actual", "hard"),
    [
        (_source(600, compression=zipfile.ZIP_STORED), "upload", 1_412, 1_200),
        (_source(600, compression=zipfile.ZIP_DEFLATED), "decompressed", 1_200, 1_000),
    ],
)
def test_confirmation_cannot_exceed_either_hard_limit(
    service, source, dimension, actual, hard
) -> None:
    client, actor, _settings = service
    response = client.post(
        "/api/v1/conversions",
        headers={"X-CSRF-Token": actor["csrf_token"]},
        files={"source": ("source.zip", source)},
        data={"output": "docx", "allow_large_archive": "true"},
    )
    assert response.status_code == 413
    error = response.json()["error"]
    assert (
        error["code"],
        error["dimension"],
        error["actual_bytes"],
        error["hard_limit_bytes"],
    ) == (
        "CONVERSION_SIZE_LIMIT_EXCEEDED",
        dimension,
        actual,
        hard,
    )
    assert client.get("/api/v1/conversions").json()["total"] == 0
    assert _override_audit(client) == []


def _override_audit(client: TestClient) -> list[dict]:
    return [
        record
        for record in client.get("/api/v1/audit").json()
        if record["operation"] == "large_archive_override"
    ]
