import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from fastapi import UploadFile

from backend.config import settings
from backend.ingestion.parser import (
    IngestionError,
    ParsedRow,
    inspect_file,
    iter_records,
)
from backend.ingestion.schemas import ImportRequest
from data.ingestion_repository import IngestionRepository


ALLOWED_EXTENSIONS = {".csv": "CSV", ".xlsx": "XLSX"}
ALLOWED_MIME = {
    "CSV": {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "text/plain",
        "application/octet-stream",
    },
    "XLSX": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/octet-stream",
    },
}
TYPE_RULES: dict[str, set[str]] = {
    "timestamp": {"DATE_TIME"},
    "revenue": {"NUMBER", "CURRENCY"},
    "event_id": {"STRING"},
    "customer_id": {"STRING"},
    "category": {"STRING"},
    "region": {"STRING"},
    "source": {"STRING"},
    "product": {"STRING"},
    "currency": {"STRING"},
    "is_conversion": {"BOOLEAN"},
}
REQUIRED_FIELDS = {"timestamp", "revenue"}
NUMBER_PATTERN = re.compile(r"^[-+]?(?:\d+(?:\.\d+)?|\.\d+)$")


class IngestionService:
    def __init__(self, repository: IngestionRepository, upload_dir: Path):
        self.repository = repository
        self.upload_dir = upload_dir.resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: UploadFile, workspace_id: int, user_id: int) -> dict:
        original = self._safe_filename(file.filename or "")
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise IngestionError(
                "UNSUPPORTED_EXTENSION", "Only .csv and .xlsx files are supported", 415
            )
        file_type = ALLOWED_EXTENSIONS[suffix]
        content_type = (
            (file.content_type or "application/octet-stream").lower().split(";", 1)[0]
        )
        if content_type not in ALLOWED_MIME[file_type]:
            raise IngestionError(
                "UNSUPPORTED_MIME_TYPE",
                f"Content type {content_type} is not valid for {suffix}",
                415,
            )

        job_id = uuid.uuid4().hex
        stored_filename = f"{job_id}{suffix}"
        destination = self._storage_path(stored_filename)
        digest = hashlib.sha256()
        size = 0
        try:
            with destination.open("xb") as handle:
                while chunk := await file.read(64 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise IngestionError(
                            "FILE_TOO_LARGE",
                            f"Files may be at most {settings.max_upload_bytes} bytes",
                            413,
                        )
                    digest.update(chunk)
                    handle.write(chunk)
            if size == 0:
                raise IngestionError("EMPTY_FILE", "The uploaded file is empty")
            if file_type == "XLSX":
                with destination.open("rb") as uploaded:
                    if uploaded.read(4) != b"PK\x03\x04":
                        raise IngestionError(
                            "MALFORMED_XLSX", "The XLSX signature is invalid"
                        )
            completed = self.repository.completed_for_hash(
                workspace_id, digest.hexdigest()
            )
            if completed:
                raise IngestionError(
                    "DUPLICATE_IMPORT",
                    f"This file was already imported by job {completed['id']}",
                    409,
                )
            return self.repository.create_job(
                {
                    "id": job_id,
                    "workspace_id": workspace_id,
                    "created_by": user_id,
                    "original_filename": original,
                    "stored_filename": stored_filename,
                    "file_hash": digest.hexdigest(),
                    "file_size": size,
                    "mime_type": content_type,
                    "file_type": file_type,
                }
            )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    def preview(self, job_id: str, workspace_id: int, sheet_name: str | None) -> dict:
        job = self._job(job_id, workspace_id)
        if job["status"] not in {"UPLOADED", "PREVIEWED"}:
            raise IngestionError(
                "INVALID_JOB_STATE",
                f"Job cannot be previewed from state {job['status']}",
                409,
            )
        try:
            preview = inspect_file(self._job_path(job), job["file_type"], sheet_name)
            updated = self.repository.save_preview(job_id, workspace_id, preview)
            if not updated:
                raise IngestionError(
                    "INVALID_JOB_STATE",
                    "The job state changed before preview completed",
                    409,
                )
            return {
                "job": updated,
                "preview": preview,
                "processing_mode": "synchronous",
            }
        except IngestionError as exc:
            self.repository.set_status(
                job_id, workspace_id, "FAILED", error_summary=exc.message
            )
            raise

    def run_import(
        self, job_id: str, workspace_id: int, payload: ImportRequest
    ) -> dict:
        job = self._job(job_id, workspace_id)
        if job["status"] != "PREVIEWED":
            raise IngestionError(
                "INVALID_JOB_STATE", "Preview the file before importing", 409
            )
        duplicate = self.repository.completed_for_hash(
            workspace_id, job["file_hash"], exclude_job_id=job_id
        )
        if duplicate:
            raise IngestionError(
                "DUPLICATE_IMPORT",
                f"This file was already imported by job {duplicate['id']}",
                409,
            )
        mapping = self._validate_mapping(job, payload)
        selected_sheet = payload.sheet_name or job.get("sheet_name")
        if not self.repository.begin_validation(
            job_id, workspace_id, selected_sheet, mapping
        ):
            raise IngestionError(
                "INVALID_JOB_STATE", "The import job cannot start", 409
            )
        self.repository.reset_details(job_id)

        row_count = valid_rows = invalid_rows = 0
        raw_batch: list[tuple[int, str, str]] = []
        error_batch: list[dict] = []
        seen_ids: set[str] = set()
        try:
            for parsed in iter_records(
                self._job_path(job), job["file_type"], selected_sheet
            ):
                row_count += 1
                raw_json = json.dumps(parsed.values, ensure_ascii=False, sort_keys=True)
                raw_batch.append(
                    (
                        parsed.row_number,
                        raw_json,
                        hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
                    )
                )
                _normalized, errors = self._validate_row(
                    parsed, mapping, job_id, seen_ids
                )
                if errors:
                    invalid_rows += 1
                    error_batch.extend(errors)
                else:
                    valid_rows += 1
                if len(raw_batch) >= 500:
                    self.repository.add_raw_records(job_id, raw_batch)
                    raw_batch.clear()
                if len(error_batch) >= 500:
                    self.repository.add_errors(job_id, error_batch)
                    error_batch.clear()
            self.repository.add_raw_records(job_id, raw_batch)
            self.repository.add_errors(job_id, error_batch)
        except IngestionError as exc:
            self.repository.finish_validation(
                job_id, workspace_id, row_count, valid_rows, max(1, invalid_rows), True
            )
            self.repository.set_status(
                job_id, workspace_id, "FAILED", error_summary=exc.message
            )
            raise

        should_fail = invalid_rows > 0 and (
            not payload.allow_partial or valid_rows == 0
        )
        self.repository.finish_validation(
            job_id, workspace_id, row_count, valid_rows, invalid_rows, should_fail
        )
        if should_fail:
            return {
                "job": self._job(job_id, workspace_id),
                "processing_mode": "synchronous",
            }

        refreshed = self._job(job_id, workspace_id)
        seen_ids.clear()

        def normalized_rows() -> Iterator[tuple[int, dict]]:
            for parsed in iter_records(
                self._job_path(refreshed), refreshed["file_type"], selected_sheet
            ):
                normalized, errors = self._validate_row(
                    parsed, mapping, job_id, seen_ids
                )
                if not errors and normalized:
                    yield parsed.row_number, normalized

        try:
            result = self.repository.complete_import(
                refreshed, payload.display_name, normalized_rows(), valid_rows
            )
        except sqlite3.IntegrityError as exc:
            self.repository.fail_processing(
                job_id, workspace_id, "A duplicate completed import already exists"
            )
            raise IngestionError(
                "DUPLICATE_IMPORT", "This file has already been imported", 409
            ) from exc
        except IngestionError:
            self.repository.fail_processing(
                job_id, workspace_id, "The file became invalid during processing"
            )
            raise
        except Exception as exc:
            self.repository.fail_processing(
                job_id, workspace_id, "Import processing failed"
            )
            raise IngestionError("IMPORT_FAILED", "Import processing failed") from exc
        return {
            "job": self._job(job_id, workspace_id),
            "data_source": self.repository.get_source(
                result["source_id"], workspace_id
            ),
            "processing_mode": "synchronous",
        }

    def _validate_mapping(
        self, job: dict, payload: ImportRequest
    ) -> dict[str, dict[str, str]]:
        preview = job.get("preview") or {}
        available = set(preview.get("columns") or [])
        mapped: dict[str, dict[str, str]] = {
            field.canonical_field: {
                "source_column": field.source_column,
                "canonical_field": field.canonical_field,
                "data_type": field.data_type,
            }
            for field in payload.fields
        }
        missing = sorted(REQUIRED_FIELDS - set(mapped))
        if missing:
            raise IngestionError(
                "MISSING_REQUIRED_MAPPING",
                f"Required canonical mappings are missing: {', '.join(missing)}",
            )
        unknown = sorted({field.source_column for field in payload.fields} - available)
        if unknown:
            raise IngestionError(
                "UNKNOWN_SOURCE_COLUMN",
                f"Mapped source columns do not exist: {', '.join(unknown)}",
            )
        for canonical, item in mapped.items():
            if item["data_type"] not in TYPE_RULES[canonical]:
                raise IngestionError(
                    "INVALID_MAPPING_TYPE",
                    f"{canonical} does not support {item['data_type']}",
                )
        if (
            job["file_type"] == "XLSX"
            and payload.sheet_name
            and payload.sheet_name not in (preview.get("sheet_names") or [])
        ):
            raise IngestionError(
                "SHEET_NOT_FOUND", "The selected worksheet does not exist", 404
            )
        return mapped

    def _validate_row(
        self,
        parsed: ParsedRow,
        mapping: dict[str, dict[str, str]],
        job_id: str,
        seen_ids: set[str],
    ) -> tuple[dict[str, Any] | None, list[dict]]:
        normalized: dict[str, Any] = {}
        errors: list[dict] = []
        for canonical, item in mapping.items():
            source = item["source_column"]
            raw = parsed.values.get(source)
            if source in parsed.formula_fields:
                errors.append(
                    self._row_error(
                        parsed.row_number,
                        canonical,
                        "UNSUPPORTED_FORMULA",
                        "Spreadsheet formulas are not imported",
                        raw,
                    )
                )
                continue
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                if canonical in REQUIRED_FIELDS:
                    errors.append(
                        self._row_error(
                            parsed.row_number,
                            canonical,
                            "MISSING_REQUIRED",
                            "A required value is missing",
                            raw,
                        )
                    )
                else:
                    normalized[canonical] = None
                continue
            try:
                normalized[canonical] = self._convert(raw, item["data_type"])
            except ValueError:
                code = {
                    "DATE_TIME": "INVALID_DATE",
                    "NUMBER": "INVALID_NUMBER",
                    "CURRENCY": "INVALID_NUMBER",
                    "BOOLEAN": "INVALID_BOOLEAN",
                }.get(item["data_type"], "INVALID_VALUE")
                errors.append(
                    self._row_error(
                        parsed.row_number,
                        canonical,
                        code,
                        f"Value is not a valid {item['data_type'].lower()}",
                        raw,
                    )
                )

        if not errors:
            provided_event = normalized.get("event_id")
            if provided_event:
                event_id = str(provided_event)
                if event_id in seen_ids:
                    errors.append(
                        self._row_error(
                            parsed.row_number,
                            "event_id",
                            "DUPLICATE_VALUE",
                            "event_id is duplicated within this file",
                            event_id,
                        )
                    )
                seen_ids.add(event_id)
            else:
                normalized["event_id"] = f"{job_id}-{parsed.row_number}"
            normalized.setdefault("is_conversion", True)
        return (normalized if not errors else None), errors

    def _convert(self, value: Any, data_type: str) -> Any:
        if data_type == "STRING":
            return str(value).strip()
        if data_type == "BOOLEAN":
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in {"true", "yes", "1"}:
                return True
            if text in {"false", "no", "0"}:
                return False
            raise ValueError
        if data_type == "NUMBER":
            if isinstance(value, bool):
                raise ValueError
            if isinstance(value, (int, float)):
                return float(value)
            text = str(value).strip().replace(",", "")
            if not NUMBER_PATTERN.fullmatch(text):
                raise ValueError
            return float(text)
        if data_type == "CURRENCY":
            if isinstance(value, bool):
                raise ValueError
            if isinstance(value, (int, float)):
                return float(value)
            text = re.sub(r"(?i)(VND|USD|EUR|GBP)|[$€£¥₫]|\s", "", str(value)).replace(
                ",", ""
            )
            if not NUMBER_PATTERN.fullmatch(text):
                raise ValueError
            return float(text)
        if data_type == "DATE_TIME":
            if isinstance(value, datetime):
                return value.isoformat()
            if not isinstance(value, str):
                raise ValueError
            text = value.strip()
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
            except ValueError:
                for fmt in (
                    "%Y-%m-%d",
                    "%Y/%m/%d",
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                    "%Y-%m-%d %H:%M:%S",
                ):
                    try:
                        return datetime.strptime(text, fmt).isoformat()
                    except ValueError:
                        continue
                raise ValueError
        raise ValueError

    def _row_error(
        self, row_number: int, field: str, code: str, message: str, raw: Any
    ) -> dict:
        return {
            "row_number": row_number,
            "field": field,
            "code": code,
            "message": message,
            "raw_value": None if raw is None else str(raw)[:500],
        }

    def _safe_filename(self, filename: str) -> str:
        name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        name = "".join(character for character in name if character.isprintable())
        if not name or name in {".", ".."} or len(name) > 255:
            raise IngestionError("INVALID_FILENAME", "The uploaded filename is invalid")
        return name

    def _storage_path(self, stored_filename: str) -> Path:
        candidate = (self.upload_dir / stored_filename).resolve()
        if candidate.parent != self.upload_dir:
            raise IngestionError(
                "UNSAFE_PATH", "The generated upload path is invalid", 400
            )
        return candidate

    def _job_path(self, job: dict) -> Path:
        path = self._storage_path(job["stored_filename"])
        if not path.is_file():
            raise IngestionError(
                "UPLOAD_NOT_FOUND", "The stored upload is unavailable", 404
            )
        return path

    def _job(self, job_id: str, workspace_id: int) -> dict:
        job = self.repository.get_job(job_id, workspace_id)
        if not job:
            raise IngestionError("IMPORT_JOB_NOT_FOUND", "Import job not found", 404)
        return job
