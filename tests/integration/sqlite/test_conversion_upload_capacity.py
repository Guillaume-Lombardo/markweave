"""Measure upload admission with real authentication, spooling, and SQLite."""

import asyncio
import os
import tracemalloc
from pathlib import Path
from threading import Barrier, Event

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from starlette import formparsers

from markweave.app import create_app
from markweave.config import Settings
from markweave.malware import MalwareScannerUnavailableError
from tests.functional.test_conversion_api import login
from tests.settings import template_settings

pytestmark = [pytest.mark.integration, pytest.mark.light_coverage]
CONVERSIONS = "/api/v1/conversions"
SOURCE_BYTES = 3_900_000
ADMIN_PASSWORD = "admin-" + "password"
CONTENT_TYPE = "multipart/form-data; boundary=upload-pressure"


async def _large_body(uploaded: asyncio.Barrier, finish_upload: asyncio.Event):
    yield (
        b'--upload-pressure\r\nContent-Disposition: form-data; name="output"\r\n\r\n'
        b'docx\r\n--upload-pressure\r\nContent-Disposition: form-data; name="source"; '
        b'filename="large.md"\r\n\r\n'
    )
    chunk = b"x" * 65_536
    chunk_count, residual = divmod(SOURCE_BYTES, len(chunk))
    for _ in range(chunk_count):
        yield chunk
    yield chunk[:residual]
    await uploaded.wait()
    await finish_upload.wait()
    yield b"\r\n--upload-pressure--\r\n"


async def _unread_body():
    pytest.fail("Saturated upload must be rejected before reading its body")
    yield b""


async def _assert_saturated(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    denied = await client.post(CONVERSIONS, headers=headers, content=_unread_body())
    assert denied.status_code == 503
    assert denied.headers["Retry-After"] == "2"
    assert denied.json()["error"]["code"] == "CONVERSION_UPLOAD_CAPACITY_EXCEEDED"


async def _assert_retry(
    client: httpx.AsyncClient, headers: dict[str, str], spool
) -> None:
    invalid = await client.post(
        CONVERSIONS,
        headers=headers,
        data={"output": "invalid"},
        files={"source": ("source.md", b"# Invalid output")},
    )
    assert invalid.status_code == 422
    assert spool.spy_return.closed
    accepted = await client.post(
        CONVERSIONS,
        headers=headers,
        data={"output": "docx"},
        files={"source": ("source.md", b"# Accepted after cleanup")},
    )
    assert accepted.status_code == 202
    assert spool.spy_return.closed
    assert (await client.get(CONVERSIONS, headers=headers)).json()["total"] == 1


@pytest.fixture
def service(tmp_path: Path):
    settings = Settings(
        **template_settings(),
        storage_profile="standalone",
        standalone_data_directory=tmp_path,
        initial_admin_username="admin",
        initial_admin_password=ADMIN_PASSWORD,
        argon2_memory_cost=8,
        argon2_time_cost=1,
        conversion_upload_max_bytes=1_000_000,
        conversion_request_max_bytes=1_100_000,
        conversion_retry_after_seconds=2,
        job_result_retention_seconds=3_600,
    )
    slot_count = settings.conversion_upload_max_in_flight
    scanners_entered = Barrier(slot_count + 1, timeout=15)
    finish_scan = Event()

    class PausedScanner:
        def scan(self, content: bytes) -> None:
            if len(content) == SOURCE_BYTES:
                scanners_entered.wait()
                assert finish_scan.wait(timeout=15)
                raise MalwareScannerUnavailableError

    app = create_app(settings, scanner=PausedScanner())

    def sign_in(client: TestClient, username: str, password: str) -> dict[str, str]:
        client.cookies.clear()
        actor = login(client, username, password)
        cookie = client.cookies[settings.session_cookie_name]
        return {
            "Cookie": f"{settings.session_cookie_name}={cookie}",
            "X-CSRF-Token": actor["csrf_token"],
        }

    with TestClient(app, base_url="https://testserver") as admin:
        admin_headers = sign_in(admin, "admin", ADMIN_PASSWORD)
        users = {}
        for username in ("alice", "bob"):
            password = f"{username}-password"
            created = admin.post(
                "/api/v1/admin/users",
                headers=admin_headers,
                json={"username": username, "password": password},
            )
            assert created.status_code == 201
            users[username] = sign_in(admin, username, password)
        yield (
            app,
            admin,
            admin_headers,
            users,
            slot_count,
            scanners_entered,
            finish_scan,
        )


def test_authenticated_upload_pressure(
    service, mocker: MockerFixture, record_property
) -> None:
    app, admin, admin_headers, users, slot_count, scanners_entered, finish_scan = (
        service
    )
    spool = mocker.spy(formparsers, "SpooledTemporaryFile")

    async def exercise(alice: dict[str, str], bob: dict[str, str]) -> None:
        uploaded = asyncio.Barrier(slot_count + 1)
        finish_upload = asyncio.Event()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://testserver"
        ) as client:
            upload_headers = {**alice, "Content-Type": CONTENT_TYPE}
            reject_headers = {**bob, "Content-Type": CONTENT_TYPE}
            tracemalloc.start()
            tasks = [
                asyncio.create_task(
                    client.post(
                        CONVERSIONS,
                        headers=upload_headers,
                        content=_large_body(uploaded, finish_upload),
                    )
                )
                for _ in range(slot_count)
            ]
            try:
                async with asyncio.timeout(15):
                    await uploaded.wait()
                    files = tuple(spool.spy_return_list)
                    assert (
                        sum(file.tell() for file in files) == slot_count * SOURCE_BYTES
                    )
                    spool_bytes = sum(os.fstat(file.fileno()).st_size for file in files)
                    assert 0 < spool_bytes <= slot_count * SOURCE_BYTES
                    record_property("concurrent_spool_bytes", spool_bytes)
                    record_property(
                        "spooling_python_peak_bytes", tracemalloc.get_traced_memory()[1]
                    )

                    await _assert_saturated(client, reject_headers)
                    anonymous = await client.post(
                        CONVERSIONS,
                        headers={"Content-Type": CONTENT_TYPE},
                        content=_unread_body(),
                    )
                    assert anonymous.status_code == 401
                    assert spool.call_count == slot_count

                    finish_upload.set()
                    await asyncio.to_thread(scanners_entered.wait)
                    assert all(file.closed for file in files)
                    record_property(
                        "scanning_python_peak_bytes", tracemalloc.get_traced_memory()[1]
                    )
                    await _assert_saturated(client, reject_headers)
                    assert spool.call_count == slot_count
            finally:
                finish_scan.set()
                finish_upload.set()
                try:
                    async with asyncio.timeout(16):
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                finally:
                    tracemalloc.stop()

            for result in results:
                assert isinstance(result, httpx.Response)
                assert result.status_code == 503
                assert result.json()["error"]["code"] == "UPLOAD_SCANNER_UNAVAILABLE"
            assert (await client.get(CONVERSIONS, headers=alice)).json()["total"] == 0
            assert (await client.get(CONVERSIONS, headers=bob)).json()["total"] == 0

            await _assert_retry(client, bob, spool)

    assert admin.portal is not None
    admin.portal.call(exercise, users["alice"], users["bob"])
    audit = admin.get("/api/v1/audit", headers=admin_headers)
    assert audit.status_code == 200
    assert not any(
        record["operation"] == "large_archive_override" for record in audit.json()
    )
