from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from backend.auth.dependencies import AuthContext, require_admin, require_csrf
from backend.ingestion.schemas import CANONICAL_SCHEMA, ImportRequest, PreviewRequest
from backend.ingestion.service import IngestionService
from backend.query import PageSpec, query_meta
from backend.responses import success_response
from data.ingestion_repository import IngestionRepository


router = APIRouter(prefix="/api/ingestion", tags=["data-ingestion"])


def get_ingestion_service(request: Request) -> IngestionService:
    repository = IngestionRepository(Path(request.app.state.database_path))
    return IngestionService(repository, Path(request.app.state.upload_dir))


@router.get("/schema")
def canonical_schema(_context: AuthContext = Depends(require_admin)):
    return success_response(
        {"fields": CANONICAL_SCHEMA, "supported_file_types": ["CSV", "XLSX"]}
    )


@router.post("/uploads", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    context: AuthContext = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
    service: IngestionService = Depends(get_ingestion_service),
):
    job = await service.upload(file, context.workspace_id, context.user_id)
    return success_response(
        {"job": job, "next_status": "UPLOADED", "processing_mode": "synchronous"}
    )


@router.post("/jobs/{job_id}/preview")
def preview_file(
    job_id: str,
    payload: PreviewRequest,
    context: AuthContext = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
    service: IngestionService = Depends(get_ingestion_service),
):
    return success_response(
        service.preview(job_id, context.workspace_id, payload.sheet_name)
    )


@router.post("/jobs/{job_id}/import")
def import_file(
    job_id: str,
    payload: ImportRequest,
    context: AuthContext = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
    service: IngestionService = Depends(get_ingestion_service),
):
    return success_response(service.run_import(job_id, context.workspace_id, payload))


@router.get("/jobs")
def list_import_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default="", max_length=200),
    status: str | None = Query(
        default=None,
        pattern="^(UPLOADED|PREVIEWED|VALIDATING|PROCESSING|COMPLETED|FAILED|CANCELLED)$",
    ),
    file_type: str | None = Query(default=None, pattern="^(CSV|XLSX)$"),
    sort_by: str = Query(
        default="created_at",
        pattern="^(created_at|status|original_filename|row_count)$",
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    context: AuthContext = Depends(require_admin),
    service: IngestionService = Depends(get_ingestion_service),
):
    rows, total = service.repository.query_jobs(
        context.workspace_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        file_type=file_type,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return success_response(
        rows,
        meta=query_meta(
            PageSpec(page, page_size),
            total,
            search=search,
            filters={"status": status, "file_type": file_type},
            sort_by=sort_by,
            sort_order=sort_order,
        ),
    )


@router.get("/jobs/{job_id}")
def get_import_job(
    job_id: str,
    context: AuthContext = Depends(require_admin),
    service: IngestionService = Depends(get_ingestion_service),
):
    return success_response(service._job(job_id, context.workspace_id))


@router.get("/jobs/{job_id}/errors")
def get_import_errors(
    job_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: AuthContext = Depends(require_admin),
    service: IngestionService = Depends(get_ingestion_service),
):
    result = service.repository.list_errors(job_id, context.workspace_id, limit, offset)
    if result is None:
        service._job(job_id, context.workspace_id)
    return success_response(result)


@router.post("/jobs/{job_id}/cancel")
def cancel_import_job(
    job_id: str,
    context: AuthContext = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
    service: IngestionService = Depends(get_ingestion_service),
):
    service._job(job_id, context.workspace_id)
    if not service.repository.cancel(job_id, context.workspace_id):
        from backend.ingestion.parser import IngestionError

        raise IngestionError(
            "INVALID_JOB_STATE", "Only uploaded or previewed jobs can be cancelled", 409
        )
    return success_response(service._job(job_id, context.workspace_id))


@router.get("/sources/{source_id}/history")
def source_import_history(
    source_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    context: AuthContext = Depends(require_admin),
    service: IngestionService = Depends(get_ingestion_service),
):
    history = service.repository.source_history(source_id, context.workspace_id, limit)
    if history is None:
        from backend.ingestion.parser import IngestionError

        raise IngestionError("DATA_SOURCE_NOT_FOUND", "Data source not found", 404)
    return success_response(history)
