import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from data.database import connection


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestionRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def create_job(self, values: dict) -> dict:
        now = now_iso()
        with connection(self.database_path) as conn:
            conn.execute(
                """INSERT INTO import_jobs
                   (id,workspace_id,created_by,original_filename,stored_filename,file_hash,file_size,mime_type,file_type,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,'UPLOADED',?,?)""",
                (
                    values["id"],
                    values["workspace_id"],
                    values["created_by"],
                    values["original_filename"],
                    values["stored_filename"],
                    values["file_hash"],
                    values["file_size"],
                    values["mime_type"],
                    values["file_type"],
                    now,
                    now,
                ),
            )
            return self._job_row(conn, values["id"], values["workspace_id"])

    def _job_row(self, conn, job_id: str, workspace_id: int) -> dict:
        row = conn.execute(
            """SELECT j.*,u.full_name uploader_name,u.email uploader_email,d.name source_name
               FROM import_jobs j JOIN users u ON u.id=j.created_by
               LEFT JOIN data_sources d ON d.id=j.data_source_id
               WHERE j.id=? AND j.workspace_id=?""",
            (job_id, workspace_id),
        ).fetchone()
        return dict(row) if row else {}

    def get_job(self, job_id: str, workspace_id: int) -> Optional[dict]:
        with connection(self.database_path) as conn:
            row = self._job_row(conn, job_id, workspace_id)
            if not row:
                return None
            return self._deserialize_job(row)

    def list_jobs(self, workspace_id: int, limit: int = 50) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT j.*,u.full_name uploader_name,u.email uploader_email,d.name source_name
                   FROM import_jobs j JOIN users u ON u.id=j.created_by
                   LEFT JOIN data_sources d ON d.id=j.data_source_id
                   WHERE j.workspace_id=? ORDER BY j.created_at DESC LIMIT ?""",
                (workspace_id, limit),
            ).fetchall()
            return [self._deserialize_job(dict(row)) for row in rows]

    def query_jobs(
        self,
        workspace_id: int,
        *,
        page: int,
        page_size: int,
        search: str = "",
        status: str | None = None,
        file_type: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict], int]:
        if sort_by not in {"created_at", "status", "original_filename", "row_count"}:
            raise ValueError("Unsupported import sort")
        if sort_order not in {"asc", "desc"}:
            raise ValueError("Unsupported import sort order")
        clauses = ["j.workspace_id=?"]
        params: list[object] = [workspace_id]
        if search:
            escaped = (
                search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            clauses.append(
                "(j.original_filename LIKE ? ESCAPE '\\' OR d.name LIKE ? ESCAPE '\\' OR u.full_name LIKE ? ESCAPE '\\')"
            )
            params.extend([f"%{escaped}%"] * 3)
        if status:
            clauses.append("j.status=?")
            params.append(status)
        if file_type:
            clauses.append("j.file_type=?")
            params.append(file_type)
        where = " AND ".join(clauses)
        joins = """FROM import_jobs j JOIN users u ON u.id=j.created_by
                   LEFT JOIN data_sources d ON d.id=j.data_source_id"""
        with connection(self.database_path) as conn:
            total = conn.execute(
                f"SELECT COUNT(*) {joins} WHERE {where}", tuple(params)
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT j.*,u.full_name uploader_name,u.email uploader_email,d.name source_name
                    {joins} WHERE {where}
                    ORDER BY j.{sort_by} {sort_order.upper()},j.created_at DESC LIMIT ? OFFSET ?""",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
            return [self._deserialize_job(dict(row)) for row in rows], total

    def _deserialize_job(self, row: dict) -> dict:
        for key in ("mapping_json", "preview_json"):
            if row.get(key):
                row[key.removesuffix("_json")] = json.loads(row[key])
            row.pop(key, None)
        return row

    def completed_for_hash(
        self, workspace_id: int, file_hash: str, exclude_job_id: str | None = None
    ) -> Optional[dict]:
        query = "SELECT id,status,completed_at FROM import_jobs WHERE workspace_id=? AND file_hash=? AND status='COMPLETED'"
        params: tuple[object, ...] = (workspace_id, file_hash)
        if exclude_job_id:
            query += " AND id<>?"
            params += (exclude_job_id,)
        query += " LIMIT 1"
        with connection(self.database_path) as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def save_preview(
        self, job_id: str, workspace_id: int, preview: dict
    ) -> Optional[dict]:
        now = now_iso()
        with connection(self.database_path) as conn:
            changed = conn.execute(
                """UPDATE import_jobs SET status='PREVIEWED',sheet_name=?,row_count=?,column_count=?,preview_json=?,error_summary=NULL,updated_at=?
                   WHERE id=? AND workspace_id=? AND status IN ('UPLOADED','PREVIEWED')""",
                (
                    preview.get("selected_sheet"),
                    preview["row_count"],
                    preview["column_count"],
                    json.dumps(preview, ensure_ascii=False),
                    now,
                    job_id,
                    workspace_id,
                ),
            ).rowcount
            return (
                self._deserialize_job(self._job_row(conn, job_id, workspace_id))
                if changed
                else None
            )

    def set_status(
        self,
        job_id: str,
        workspace_id: int,
        status: str,
        *,
        error_summary: str | None = None,
    ) -> bool:
        with connection(self.database_path) as conn:
            return (
                conn.execute(
                    "UPDATE import_jobs SET status=?,error_summary=?,updated_at=? WHERE id=? AND workspace_id=?",
                    (status, error_summary, now_iso(), job_id, workspace_id),
                ).rowcount
                > 0
            )

    def begin_validation(
        self, job_id: str, workspace_id: int, sheet_name: str | None, mapping: dict
    ) -> bool:
        with connection(self.database_path) as conn:
            return (
                conn.execute(
                    """UPDATE import_jobs SET status='VALIDATING',sheet_name=?,mapping_json=?,valid_rows=0,invalid_rows=0,error_summary=NULL,updated_at=?
                   WHERE id=? AND workspace_id=? AND status IN ('UPLOADED','PREVIEWED','FAILED')""",
                    (
                        sheet_name,
                        json.dumps(mapping, ensure_ascii=False),
                        now_iso(),
                        job_id,
                        workspace_id,
                    ),
                ).rowcount
                > 0
            )

    def reset_details(self, job_id: str) -> None:
        with connection(self.database_path) as conn:
            conn.execute("DELETE FROM import_errors WHERE job_id=?", (job_id,))
            conn.execute("DELETE FROM raw_import_records WHERE job_id=?", (job_id,))

    def add_raw_records(self, job_id: str, rows: list[tuple[int, str, str]]) -> None:
        if not rows:
            return
        with connection(self.database_path) as conn:
            conn.executemany(
                "INSERT INTO raw_import_records (job_id,row_number,payload_json,row_hash) VALUES (?,?,?,?)",
                [(job_id, *row) for row in rows],
            )

    def add_errors(self, job_id: str, errors: list[dict]) -> None:
        if not errors:
            return
        with connection(self.database_path) as conn:
            conn.executemany(
                """INSERT INTO import_errors (job_id,row_number,field_name,error_code,message,raw_value)
                   VALUES (?,?,?,?,?,?)""",
                [
                    (
                        job_id,
                        error["row_number"],
                        error["field"],
                        error["code"],
                        error["message"],
                        error.get("raw_value"),
                    )
                    for error in errors
                ],
            )

    def finish_validation(
        self,
        job_id: str,
        workspace_id: int,
        row_count: int,
        valid_rows: int,
        invalid_rows: int,
        failed: bool,
    ) -> None:
        status = "FAILED" if failed else "PROCESSING"
        summary = (
            f"{invalid_rows} of {row_count} rows failed validation"
            if invalid_rows
            else None
        )
        with connection(self.database_path) as conn:
            conn.execute(
                """UPDATE import_jobs SET status=?,row_count=?,valid_rows=?,invalid_rows=?,error_summary=?,updated_at=?
                   WHERE id=? AND workspace_id=?""",
                (
                    status,
                    row_count,
                    valid_rows,
                    invalid_rows,
                    summary,
                    now_iso(),
                    job_id,
                    workspace_id,
                ),
            )

    def complete_import(
        self,
        job: dict,
        display_name: str,
        normalized_rows: Iterable[tuple[int, dict]],
        valid_count: int,
    ) -> dict:
        now = now_iso()
        with connection(self.database_path) as conn:
            source_cursor = conn.execute(
                """INSERT INTO data_sources
                   (name,source_type,status,last_sync,workspace_id,created_by,created_at,last_import_at,event_count,health_status)
                   VALUES (?,'FILE_UPLOAD','connected',?,?,?,?,?,?,?)""",
                (
                    display_name,
                    now,
                    job["workspace_id"],
                    job["created_by"],
                    now,
                    now,
                    valid_count,
                    "HEALTHY" if job["invalid_rows"] == 0 else "PARTIAL",
                ),
            )
            source_id = source_cursor.lastrowid
            batch: list[tuple] = []
            inserted = 0
            for row_number, row in normalized_rows:
                batch.append(
                    (
                        row["event_id"],
                        row.get("customer_id"),
                        row.get("category"),
                        row.get("region"),
                        row["revenue"],
                        row["timestamp"],
                        job["workspace_id"],
                        job["id"],
                        source_id,
                        row.get("source"),
                        row.get("product"),
                        row.get("currency"),
                        1 if row.get("is_conversion", True) else 0,
                        job["id"],
                        row_number,
                    )
                )
                if len(batch) >= 500:
                    inserted += self._insert_orders(conn, batch)
                    batch.clear()
            if batch:
                inserted += self._insert_orders(conn, batch)
            if inserted != valid_count:
                raise RuntimeError(
                    "Normalized row count did not match validation result"
                )
            conn.execute(
                """UPDATE import_jobs SET status='COMPLETED',data_source_id=?,valid_rows=?,completed_at=?,updated_at=?
                   WHERE id=? AND workspace_id=?""",
                (source_id, inserted, now, now, job["id"], job["workspace_id"]),
            )
            return {"source_id": source_id, "inserted": inserted}

    def get_source(self, source_id: int, workspace_id: int) -> Optional[dict]:
        with connection(self.database_path) as conn:
            row = conn.execute(
                """SELECT id,name,source_type,status,last_sync,workspace_id,created_by,
                          created_at,last_import_at,event_count,health_status
                   FROM data_sources WHERE id=? AND workspace_id=?""",
                (source_id, workspace_id),
            ).fetchone()
            return dict(row) if row else None

    def _insert_orders(self, conn, rows: list[tuple]) -> int:
        before = conn.total_changes
        conn.executemany(
            """INSERT INTO orders
               (order_id,customer_id,category,region,amount,order_date,workspace_id,import_job_id,data_source_id,source,product,currency,is_conversion,raw_record_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,(SELECT id FROM raw_import_records WHERE job_id=? AND row_number=?))""",
            rows,
        )
        return conn.total_changes - before

    def fail_processing(self, job_id: str, workspace_id: int, summary: str) -> None:
        with connection(self.database_path) as conn:
            conn.execute(
                "DELETE FROM orders WHERE import_job_id=? AND workspace_id=?",
                (job_id, workspace_id),
            )
            conn.execute(
                "UPDATE import_jobs SET status='FAILED',error_summary=?,updated_at=? WHERE id=? AND workspace_id=?",
                (summary[:500], now_iso(), job_id, workspace_id),
            )

    def list_errors(
        self, job_id: str, workspace_id: int, limit: int, offset: int
    ) -> Optional[dict]:
        with connection(self.database_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM import_jobs WHERE id=? AND workspace_id=?",
                (job_id, workspace_id),
            ).fetchone()
            if not exists:
                return None
            total = conn.execute(
                "SELECT COUNT(*) FROM import_errors WHERE job_id=?", (job_id,)
            ).fetchone()[0]
            rows = conn.execute(
                """SELECT row_number,field_name field,error_code code,message,raw_value
                   FROM import_errors WHERE job_id=? ORDER BY row_number,id LIMIT ? OFFSET ?""",
                (job_id, limit, offset),
            ).fetchall()
            return {
                "items": [dict(row) for row in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def cancel(self, job_id: str, workspace_id: int) -> bool:
        with connection(self.database_path) as conn:
            return (
                conn.execute(
                    """UPDATE import_jobs SET status='CANCELLED',updated_at=?
                   WHERE id=? AND workspace_id=? AND status IN ('UPLOADED','PREVIEWED')""",
                    (now_iso(), job_id, workspace_id),
                ).rowcount
                > 0
            )

    def source_history(
        self, source_id: int, workspace_id: int, limit: int
    ) -> Optional[dict]:
        with connection(self.database_path) as conn:
            source = conn.execute(
                """SELECT id,name,source_type,status,last_sync,workspace_id,created_by,
                          created_at,last_import_at,event_count,health_status
                   FROM data_sources WHERE id=? AND workspace_id=?""",
                (source_id, workspace_id),
            ).fetchone()
            if not source:
                return None
            rows = conn.execute(
                """SELECT j.*,u.full_name uploader_name,u.email uploader_email,d.name source_name
                   FROM import_jobs j JOIN users u ON u.id=j.created_by LEFT JOIN data_sources d ON d.id=j.data_source_id
                   WHERE j.workspace_id=? AND j.data_source_id=? ORDER BY j.created_at DESC LIMIT ?""",
                (workspace_id, source_id, limit),
            ).fetchall()
            return {
                "source": dict(source),
                "items": [self._deserialize_job(dict(row)) for row in rows],
            }
