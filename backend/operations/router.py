import csv
import json
import logging
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from openpyxl import Workbook
from pydantic import BaseModel, Field

from backend.auth.dependencies import (
    AuthContext,
    require_admin,
    require_analyst,
    require_csrf,
    require_viewer,
)
from backend.config import settings
from backend.infrastructure.redis_client import redis_health
from backend.infrastructure.storage import create_storage
from backend.operations.repository import OperationsRepository
from backend.responses import success_response
from data.database import connection


router = APIRouter(tags=["operations"])
job_logger = logging.getLogger("nexus.jobs")
EXPORT_COLUMNS = [
    "event_id",
    "user_id",
    "session_id",
    "event_name",
    "occurred_at",
    "revenue",
    "source",
    "device",
    "region",
    "product",
]


class NotificationCreate(BaseModel):
    user_id: int | None = None
    type: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=200)


class ExportCreate(BaseModel):
    format: str = Field(pattern="^(CSV|XLSX|PDF)$")
    export_type: str = Field(default="ANALYTICS_EVENTS", pattern="^ANALYTICS_EVENTS$")


class ClientError(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    page: str = Field(default="unknown", max_length=300)
    component: str = Field(default="window", max_length=100)


def repo(request: Request) -> OperationsRepository:
    return OperationsRepository(request.app.state.database_path)


def safe_cell(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def process_export(
    database_path: Path | str | None,
    export_dir: Path,
    export_id: str,
    workspace_id: int,
    file_format: str,
    background_job_id: str,
    correlation_id: str,
    storage=None,
) -> None:
    """RQ-safe export task; local mode injects its isolated storage adapter."""
    started = time.perf_counter()
    resolved_database = database_path or settings.database_path
    repository = OperationsRepository(resolved_database)
    repository.begin_background_job(background_job_id)
    repository.begin_export(export_id, workspace_id)
    object_key = f"workspaces/{workspace_id}/exports/{export_id}.{file_format.lower()}"
    active_storage = storage or create_storage(settings)
    temporary_dir = Path(tempfile.mkdtemp(prefix="nexus-export-"))
    destination = temporary_dir / Path(object_key).name
    try:
        rows = repository.export_rows(workspace_id)
        if file_format == "CSV":
            with destination.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=EXPORT_COLUMNS, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(
                    {key: safe_cell(row.get(key)) for key in EXPORT_COLUMNS}
                    for row in rows
                )
        elif file_format == "XLSX":
            workbook = Workbook(write_only=True)
            sheet = workbook.create_sheet("Analytics Events")
            sheet.append(EXPORT_COLUMNS)
            for row in rows:
                sheet.append([safe_cell(row.get(key)) for key in EXPORT_COLUMNS])
            workbook.save(destination)
        else:
            from reportlab.lib.pagesizes import A4, landscape  # type: ignore[import-untyped]
            from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

            pdf = canvas.Canvas(str(destination), pagesize=landscape(A4))
            _width, height = landscape(A4)
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(36, height - 36, "Nexus Analytics Events")
            pdf.setFont("Helvetica", 7)
            y = height - 58
            pdf.drawString(36, y, " | ".join(EXPORT_COLUMNS))
            for row in rows:
                y -= 12
                if y < 30:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 7)
                    y = height - 36
                pdf.drawString(
                    36,
                    y,
                    " | ".join(
                        str(safe_cell(row.get(key) or ""))[:24]
                        for key in EXPORT_COLUMNS
                    ),
                )
            pdf.save()
        media_types = {
            "CSV": "text/csv",
            "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "PDF": "application/pdf",
        }
        active_storage.put_file(destination, object_key, media_types[file_format])
        repository.complete_export(export_id, workspace_id, object_key, len(rows))
        repository.finish_background_job(background_job_id, "COMPLETED")
        job_logger.info(
            json.dumps(
                {
                    "event": "job_finished",
                    "job_id": background_job_id,
                    "job_type": "EXPORT",
                    "workspace_id": workspace_id,
                    "correlation_id": correlation_id,
                    "status": "COMPLETED",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
        )
    except Exception as exc:
        repository.fail_export(
            export_id, workspace_id, f"Export generation failed: {type(exc).__name__}"
        )
        repository.finish_background_job(
            background_job_id, "FAILED", type(exc).__name__
        )
        raise
    finally:
        destination.unlink(missing_ok=True)
        temporary_dir.rmdir()


def deliver_notification_job(
    database_path: Path | str | None,
    notification_id: int,
    workspace_id: int,
    background_job_id: str,
    correlation_id: str,
) -> None:
    repository = OperationsRepository(database_path or settings.database_path)
    repository.begin_background_job(background_job_id)
    try:
        repository.deliver_notification(notification_id, workspace_id)
        repository.finish_background_job(background_job_id, "COMPLETED")
        job_logger.info(
            json.dumps(
                {
                    "event": "job_finished",
                    "job_id": background_job_id,
                    "job_type": "NOTIFICATION",
                    "workspace_id": workspace_id,
                    "correlation_id": correlation_id,
                    "status": "COMPLETED",
                }
            )
        )
    except Exception as exc:
        repository.finish_background_job(
            background_job_id, "FAILED", type(exc).__name__
        )
        raise


@router.get("/health")
@router.get("/health/live")
def liveness():
    return success_response(
        {"service": "Nexus Analytics API", "status": "live"},
        legacy={"status": "ok"},
    )


@router.post("/api/client-errors", status_code=202)
def client_error(payload: ClientError, request: Request):
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("source", "frontend")
            scope.set_tag("component", payload.component)
            scope.set_context(
                "client",
                {"page": payload.page, "request_id": request.state.request_id},
            )
            sentry_sdk.capture_message(payload.message, level="error")
    except Exception:
        job_logger.exception(
            json.dumps(
                {
                    "event": "client_error_capture_failed",
                    "request_id": request.state.request_id,
                }
            )
        )
    return success_response({"accepted": True})


@router.get("/ready")
@router.get("/health/ready")
def readiness(request: Request):
    checks = {"database": False, "redis": False, "storage": False}
    try:
        with connection(request.app.state.database_path) as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = True
        checks["storage"] = bool(request.app.state.storage.health())
        checks["redis"] = (
            redis_health(getattr(request.app.state, "redis", None))
            if settings.app_env in {"staging", "production"}
            else True
        )
    except Exception:
        pass
    if not all(checks.values()):
        raise HTTPException(503, detail={"status": "not_ready", "checks": checks})
    return success_response(
        {"status": "ready", "checks": checks}, legacy={"status": "ready"}
    )


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(request: Request):
    values = request.app.state.metrics
    average = (
        values["latency_ms_total"] / values["requests"] if values["requests"] else 0
    )
    return (
        "\n".join(
            [
                "# TYPE nexus_http_requests_total counter",
                f"nexus_http_requests_total {values['requests']}",
                "# TYPE nexus_http_errors_total counter",
                f"nexus_http_errors_total {values['errors']}",
                "# TYPE nexus_http_latency_ms_average gauge",
                f"nexus_http_latency_ms_average {average:.3f}",
            ]
        )
        + "\n"
    )


@router.get("/api/notifications")
def list_notifications(
    request: Request, context: AuthContext = Depends(require_viewer)
):
    return success_response(
        repo(request).list_notifications(context.workspace_id, context.user_id)
    )


@router.post("/api/notifications", status_code=201)
def create_notification(
    payload: NotificationCreate,
    request: Request,
    context: AuthContext = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
):
    repository = repo(request)
    item, created = repository.create_notification(
        {"workspace_id": context.workspace_id, **payload.model_dump()}
    )
    if created:
        background_id = f"notification:{item['id']}"
        repository.create_background_job(
            job_id=background_id,
            workspace_id=context.workspace_id,
            job_type="NOTIFICATION",
            resource_id=str(item["id"]),
            correlation_id=request.state.request_id,
            idempotency_key=payload.idempotency_key,
        )
        try:
            request.app.state.job_queue.enqueue(
                deliver_notification_job,
                (
                    request.app.state.database_path
                    if settings.app_env in {"development", "test"}
                    else None
                ),
                item["id"],
                context.workspace_id,
                background_id,
                request.state.request_id,
                job_id=background_id,
            )
            item = repository.get_notification(item["id"], context.workspace_id)
        except Exception as exc:
            repository.finish_background_job(
                background_id, "FAILED", type(exc).__name__
            )
            raise HTTPException(503, "Notification queue is unavailable") from exc
    repository.audit(
        workspace_id=context.workspace_id,
        actor_user_id=context.user_id,
        action="NOTIFICATION_CREATED" if created else "NOTIFICATION_DEDUPLICATED",
        resource_type="notification",
        resource_id=str(item["id"]),
        request_id=request.state.request_id,
        metadata={"type": payload.type},
    )
    return success_response({**item, "created": created})


@router.post("/api/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    request: Request,
    context: AuthContext = Depends(require_viewer),
    _csrf: None = Depends(require_csrf),
):
    if not repo(request).mark_notification_read(
        notification_id, context.workspace_id, context.user_id
    ):
        raise HTTPException(404, "Notification not found")
    return success_response({"id": notification_id, "is_read": True})


@router.post("/api/exports", status_code=202)
def create_export(
    payload: ExportCreate,
    request: Request,
    context: AuthContext = Depends(require_analyst),
    _csrf: None = Depends(require_csrf),
):
    export_id = uuid.uuid4().hex
    repository = repo(request)
    repository.create_export(
        {
            "id": export_id,
            "workspace_id": context.workspace_id,
            "created_by": context.user_id,
            "format": payload.format,
            "export_type": payload.export_type,
        }
    )
    repository.audit(
        workspace_id=context.workspace_id,
        actor_user_id=context.user_id,
        action="EXPORT_REQUESTED",
        resource_type="export",
        resource_id=export_id,
        request_id=request.state.request_id,
        metadata={"format": payload.format, "export_type": payload.export_type},
    )
    background_id = f"export:{export_id}"
    repository.create_background_job(
        job_id=background_id,
        workspace_id=context.workspace_id,
        job_type="EXPORT",
        resource_id=export_id,
        correlation_id=request.state.request_id,
        idempotency_key=request.headers.get("Idempotency-Key") or export_id,
    )
    try:
        queue_kwargs = {}
        if settings.app_env in {"development", "test"}:
            queue_kwargs["storage"] = request.app.state.storage
        request.app.state.job_queue.enqueue(
            process_export,
            (
                request.app.state.database_path
                if settings.app_env in {"development", "test"}
                else None
            ),
            Path(request.app.state.export_dir),
            export_id,
            context.workspace_id,
            payload.format,
            background_id,
            request.state.request_id,
            job_id=background_id,
            **queue_kwargs,
        )
    except Exception as exc:
        repository.fail_export(export_id, context.workspace_id, "Queue unavailable")
        repository.finish_background_job(background_id, "FAILED", type(exc).__name__)
        raise HTTPException(503, "Export queue is unavailable") from exc
    return success_response(repository.get_export(export_id, context.workspace_id))


@router.get("/api/exports")
def list_exports(request: Request, context: AuthContext = Depends(require_viewer)):
    return success_response(repo(request).list_exports(context.workspace_id))


@router.get("/api/exports/{export_id}")
def get_export(
    export_id: str, request: Request, context: AuthContext = Depends(require_viewer)
):
    item = repo(request).get_export(export_id, context.workspace_id)
    if not item:
        raise HTTPException(404, "Export not found")
    return success_response(item)


@router.get("/api/exports/{export_id}/download")
def download_export(
    export_id: str, request: Request, context: AuthContext = Depends(require_viewer)
):
    item = repo(request).get_export(export_id, context.workspace_id)
    if not item:
        raise HTTPException(404, "Export not found")
    if item["status"] != "COMPLETED" or not item.get("stored_filename"):
        raise HTTPException(409, "Export is not ready")
    object_key = item.get("object_key") or item["stored_filename"]
    if not request.app.state.storage.exists(object_key):
        raise HTTPException(404, "Export file is unavailable")
    media_types = {
        "CSV": "text/csv",
        "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "PDF": "application/pdf",
    }
    download_url = request.app.state.storage.download_url(object_key, expires=300)
    if download_url:
        return RedirectResponse(download_url, status_code=307)
    with request.app.state.storage.materialize(object_key) as path:
        return FileResponse(
            path,
            filename=f"nexus-analytics.{item['format'].lower()}",
            media_type=media_types[item["format"]],
        )


@router.get("/api/audit-logs")
def audit_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    context: AuthContext = Depends(require_admin),
):
    return success_response(repo(request).list_audit(context.workspace_id, limit))
