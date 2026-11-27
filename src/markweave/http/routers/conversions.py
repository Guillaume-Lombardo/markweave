"""Conversion submission, lifecycle, and result routes."""

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from threading import BoundedSemaphore
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from anyio import CancelScope, current_time, fail_after
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.types import Message

from markweave.auth.models import Role, User
from markweave.conversion.archive import conversion_size_limits
from markweave.conversion.document_options import MAX_TOC_DEPTH, DocumentOptions
from markweave.conversion.errors import ConversionError
from markweave.conversion.runtime_manifest import COMPONENT_VERSIONS
from markweave.conversion.size_policy import (
    ConversionSizeError,
    SizeLimit,
    require_size_confirmation,
)
from markweave.http.dependencies import HttpDependencies
from markweave.http.errors import (
    ConversionRequestTooLarge,
    ConversionUploadCapacityExceeded,
    ConversionUploadTimedOut,
    capacity_error_responses,
    error_responses,
)
from markweave.http.middleware import CONVERSION_UPLOAD_LIFETIME
from markweave.http.responses import conversion_response, template_response
from markweave.http.schemas import (
    ConversionOptionsResponse,
    ConversionPageResponse,
    ConversionResponse,
)
from markweave.jobs.errors import JobRequestError
from markweave.jobs.models import (
    ConversionJob,
    JobOutput,
    JobOutputFamily,
    JobPage,
    JobRequest,
    SourceKind,
    source_kind_for_filename,
)
from markweave.observability import CORRELATION_HEADER, CORRELATION_STATE_KEY
from markweave.persistence.errors import PersistenceError
from markweave.presentations.models import PresentationDialect, PresentationOptions
from markweave.templates.models import TemplateKind, TemplateSelectionSource

_RESULT_EXTENSIONS = {
    JobOutput.DOCX: "docx",
    JobOutput.PDF: "pdf",
    JobOutput.BOTH: "zip",
    JobOutput.PPTX: "pptx",
    JobOutput.PPTX_BUNDLE: "zip",
}


def _upload_route(dependencies: HttpDependencies) -> type[APIRoute]:
    slots = BoundedSemaphore(dependencies.settings.conversion_upload_max_in_flight)

    class ConversionUploadRoute(APIRoute):
        def get_route_handler(
            self,
        ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
            handler = super().get_route_handler()

            async def handle_upload(request: Request) -> Response:
                maximum_bytes = dependencies.settings.conversion_hard_request_max_bytes
                length = request.headers.get("Content-Length", "0")
                try:
                    declared_bytes = int(length)
                except ValueError:
                    raise JobRequestError from None
                if declared_bytes < 0:
                    raise JobRequestError
                if declared_bytes > maximum_bytes:
                    raise ConversionRequestTooLarge

                # FastAPI parses form fields before resolving endpoint dependencies.
                await run_in_threadpool(
                    dependencies.mutation_actor,
                    request,
                    request.headers.get("X-CSRF-Token"),
                )
                lifetime = getattr(request.state, CONVERSION_UPLOAD_LIFETIME)
                if not slots.acquire(blocking=False):
                    raise ConversionUploadCapacityExceeded
                lifetime.callback(slots.release)
                deadline = (
                    current_time()
                    + dependencies.settings.conversion_upload_body_timeout_seconds
                )
                received_bytes = 0

                async def receive() -> Message:
                    nonlocal received_bytes
                    remaining = deadline - current_time()
                    if remaining <= 0:
                        raise ConversionUploadTimedOut
                    try:
                        with fail_after(remaining):
                            message = await request.receive()
                    except TimeoutError:
                        raise ConversionUploadTimedOut from None
                    if current_time() >= deadline:
                        raise ConversionUploadTimedOut
                    received_bytes += len(message.get("body", b""))
                    if received_bytes > maximum_bytes:
                        raise ConversionRequestTooLarge
                    return message

                bounded_request = Request(request.scope, receive)
                try:
                    return await handler(bounded_request)
                finally:
                    # FastAPI also closes parsed forms, but its cleanup can be
                    # interrupted by the request's cancellation.
                    with CancelScope(shield=True):
                        await bounded_request.close()

            return handle_upload

    return ConversionUploadRoute


def _result_content_disposition(
    source_filename: str | None,
    output: JobOutput,
    *,
    fallback_stem: str,
) -> str:
    """Build a safe attachment header preserving the uploaded filename stem."""

    stem = (
        source_filename.rsplit(".", maxsplit=1)[0]
        if source_filename is not None
        else fallback_stem
    )
    filename = f"{stem}.{_RESULT_EXTENSIONS[output]}"
    encoded_filename = quote(filename, safe="")
    if encoded_filename != filename:
        return f"attachment; filename*=UTF-8''{encoded_filename}"
    return f'attachment; filename="{filename}"'


async def _admit_source(
    dependencies: HttpDependencies,
    source: UploadFile,
    source_kind: SourceKind,
    *,
    confirmed: bool,
) -> tuple[bytes, tuple[SizeLimit, ...]]:
    settings = dependencies.settings
    hard_upload = settings.effective_conversion_upload_hard_max_bytes
    try:
        # Multipart parsing has already counted the file bytes. Avoid reading an
        # oversized spooled file back into memory just to reject it.
        content = (
            b""
            if source.size is not None and source.size > hard_upload
            else await source.read(hard_upload + 1)
        )
    finally:
        await source.close()
    upload = SizeLimit(
        "upload",
        source.size if source.size is not None else len(content),
        settings.conversion_upload_max_bytes,
        hard_upload,
    )
    if upload.actual_bytes > hard_upload:
        raise ConversionSizeError(upload, confirmation_required=False)
    if not content:
        raise JobRequestError
    await run_in_threadpool(dependencies.components.scanner.scan, content)
    try:
        limits = await run_in_threadpool(
            conversion_size_limits,
            content,
            upload,
            settings,
            archive=source_kind is SourceKind.ARCHIVE,
        )
    except ConversionError:
        raise JobRequestError from None
    override = require_size_confirmation(limits, confirmed=confirmed)
    return content, limits if override else ()


def build_router(dependencies: HttpDependencies) -> APIRouter:
    """Build conversion routes bound to one application."""

    router = APIRouter()
    settings = dependencies.settings
    components = dependencies.components

    @router.get(
        "/api/v1/conversion-options",
        response_model=ConversionOptionsResponse,
        tags=["conversions"],
        responses=error_responses(401, 503),
    )
    def get_conversion_options(
        response: Response,
        actor: Annotated[User, Depends(dependencies.current_user)],
        template_kind: TemplateKind = TemplateKind.DOCX,
    ) -> ConversionOptionsResponse:
        response.headers["Cache-Control"] = "no-store"
        if template_kind is TemplateKind.PPTX:
            template, source = None, TemplateSelectionSource.PANDOC_DEFAULT
        else:
            template, source = dependencies.template_runtime().resolve_with_source(
                actor
            )
        version_id = template.current_version_id if template is not None else None
        if template is not None and version_id is None:
            raise PersistenceError
        return ConversionOptionsResponse(
            conversion_upload_max_bytes=settings.conversion_upload_max_bytes,
            conversion_upload_hard_max_bytes=settings.effective_conversion_upload_hard_max_bytes,
            resolved_template=(
                template_response(template, dependencies.authentication)
                if template is not None
                else None
            ),
            template_version_id=version_id,
            selection_source=source,
        )

    async def create_conversion(  # noqa: PLR0913, PLR0917 - FastAPI fields
        request: Request,
        response: Response,
        source: Annotated[UploadFile, File()],
        output: Annotated[JobOutput, Form()],
        template_id: Annotated[UUID | None, Form()] = None,
        template_version_id: Annotated[UUID | None, Form()] = None,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        presentation_dialect: Annotated[PresentationDialect | None, Form()] = None,
        slide_level: Annotated[int | None, Form(ge=1, le=6)] = None,
        toc: Annotated[bool | None, Form()] = None,
        toc_depth: Annotated[int | None, Form(ge=1, le=MAX_TOC_DEPTH)] = None,
        number_sections: Annotated[bool | None, Form()] = None,
        allow_large_archive: Annotated[bool, Form()] = False,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> ConversionResponse:
        correlation_id = getattr(request.state, CORRELATION_STATE_KEY)
        if source.filename is None:
            await source.close()
            raise JobRequestError
        source_filename = source.filename
        try:
            source_kind = source_kind_for_filename(source_filename)
        except ValueError:
            await source.close()
            raise JobRequestError from None
        content, size_override = await _admit_source(
            dependencies, source, source_kind, confirmed=allow_large_archive
        )

        def submit() -> tuple[ConversionJob, bool]:
            # The session may have been revoked while the body was read or scanned.
            actor = dependencies.mutation_actor(request, csrf_token)
            return components.jobs.submit(
                JobRequest(
                    owner_id=actor.id,
                    source=content,
                    template_id=template_id,
                    template_version_id=template_version_id,
                    output=output,
                    component_versions=COMPONENT_VERSIONS,
                    now=datetime.now(UTC),
                    correlation_id=correlation_id,
                    source_filename=source_filename,
                    source_kind=source_kind,
                    size_override=size_override,
                    document_options=(
                        DocumentOptions(toc, toc_depth, number_sections)
                        if not output.is_presentation
                        or any(
                            value is not None
                            for value in (toc, toc_depth, number_sections)
                        )
                        else None
                    ),
                    presentation_options=(
                        PresentationOptions(
                            presentation_dialect or PresentationDialect.AUTO,
                            slide_level if slide_level is not None else 2,
                        )
                        if output.is_presentation
                        or presentation_dialect is not None
                        or slide_level is not None
                        else None
                    ),
                ),
                idempotency_key,
            )

        try:
            job, _replayed = await run_in_threadpool(submit)
        except ValueError:
            raise JobRequestError from None
        response.headers["Location"] = f"/api/v1/conversions/{job.id}"
        response.headers[CORRELATION_HEADER] = job.correlation_id
        response.headers["Retry-After"] = str(settings.conversion_retry_after_seconds)
        return conversion_response(job)

    router.add_api_route(
        "/api/v1/conversions",
        create_conversion,
        methods=["POST"],
        route_class_override=_upload_route(dependencies),
        response_model=ConversionResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["conversions"],
        responses=capacity_error_responses(401, 403, 408, 409, 413, 422, 429, 503),
    )

    @router.get(
        "/api/v1/conversions",
        response_model=ConversionPageResponse,
        tags=["conversions"],
        responses=error_responses(401, 422, 503),
    )
    def list_conversions(
        actor: Annotated[User, Depends(dependencies.current_user)],
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        output_family: Annotated[
            JobOutputFamily | None,
            Query(description="Restrict results to document or presentation outputs."),
        ] = None,
        expired: Annotated[
            bool | None,
            Query(description="Restrict results by whether the job has expired."),
        ] = None,
    ) -> ConversionPageResponse:
        page: JobPage = components.jobs.list_owner(
            actor.id,
            offset=offset,
            limit=limit,
            output_family=output_family,
            expired=expired,
        )
        return ConversionPageResponse(
            items=tuple(conversion_response(job) for job in page.items),
            total=page.total,
            offset=page.offset,
            limit=page.limit,
        )

    @router.get(
        "/api/v1/conversions/{job_id}",
        response_model=ConversionResponse,
        tags=["conversions"],
        responses=error_responses(401, 404, 422, 503),
    )
    def get_conversion(
        job_id: UUID,
        actor: Annotated[User, Depends(dependencies.current_user)],
    ) -> ConversionResponse:
        return conversion_response(
            components.jobs.get_visible(
                job_id,
                actor_id=actor.id,
                actor_is_admin=actor.role is Role.ADMIN,
            )
        )

    @router.delete(
        "/api/v1/conversions/{job_id}",
        response_model=ConversionResponse,
        tags=["conversions"],
        responses=error_responses(401, 403, 404, 422, 503),
    )
    def cancel_conversion(
        job_id: UUID,
        actor: Annotated[User, Depends(dependencies.mutation_actor)],
    ) -> ConversionResponse:
        return conversion_response(
            components.jobs.cancel(
                job_id,
                actor_id=actor.id,
                actor_is_admin=actor.role is Role.ADMIN,
                now=datetime.now(UTC),
            )
        )

    @router.get(
        "/api/v1/conversions/{job_id}/result",
        response_class=Response,
        tags=["conversions"],
        responses={
            200: {
                "description": "Immutable conversion result",
                "content": {
                    "application/octet-stream": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                },
            },
            **error_responses(401, 404, 409, 422, 503),
        },
    )
    def download_conversion(
        job_id: UUID,
        actor: Annotated[User, Depends(dependencies.current_user)],
    ) -> Response:
        job, content = components.jobs.download(
            job_id,
            actor_id=actor.id,
            actor_is_admin=actor.role is Role.ADMIN,
        )
        return Response(
            content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": _result_content_disposition(
                    job.source_filename,
                    job.output,
                    fallback_stem=f"conversion-{job.id}",
                ),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get(
        "/api/v1/conversions/{job_id}/result/manifest",
        response_class=Response,
        tags=["conversions"],
        responses={
            200: {
                "description": "Canonical Word or PDF traceability manifest",
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            **error_responses(401, 404, 409, 422, 503),
        },
    )
    def download_conversion_manifest(
        job_id: UUID,
        actor: Annotated[User, Depends(dependencies.current_user)],
    ) -> Response:
        job, content = components.jobs.download_manifest(
            job_id,
            actor_id=actor.id,
            actor_is_admin=actor.role is Role.ADMIN,
        )
        return Response(
            content,
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="conversion-{job.id}-traceability.json"'
                ),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
