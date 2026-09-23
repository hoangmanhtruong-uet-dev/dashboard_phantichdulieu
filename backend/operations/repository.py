import json
from datetime import datetime, timezone
from pathlib import Path

from data.database import connection


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationsRepository:
    def __init__(self, database_path: Path | str):
        self.database_path = database_path

    def audit(
        self,
        *,
        workspace_id: int | None,
        actor_user_id: int | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        request_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        safe_metadata = {
            key: value
            for key, value in (metadata or {}).items()
            if key.lower()
            not in {"password", "token", "secret", "authorization", "cookie"}
        }
        with connection(self.database_path) as conn:
            conn.execute(
                """INSERT INTO audit_logs
                   (workspace_id,actor_user_id,action,resource_type,resource_id,request_id,metadata_json,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    workspace_id,
                    actor_user_id,
                    action,
                    resource_type,
                    resource_id,
                    request_id,
                    json.dumps(safe_metadata),
                    now_iso(),
                ),
            )

    def list_audit(self, workspace_id: int, limit: int = 100) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT a.id,a.actor_user_id,u.full_name actor_name,a.action,a.resource_type,
                          a.resource_id,a.request_id,a.metadata_json,a.created_at
                   FROM audit_logs a LEFT JOIN users u ON u.id=a.actor_user_id
                   WHERE a.workspace_id=? ORDER BY a.created_at DESC LIMIT ?""",
                (workspace_id, limit),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["metadata"] = json.loads(item.pop("metadata_json"))
                result.append(item)
            return result

    def create_notification(self, values: dict) -> tuple[dict, bool]:
        now = now_iso()
        with connection(self.database_path) as conn:
            existing = conn.execute(
                "SELECT * FROM notifications WHERE workspace_id=? AND idempotency_key=?",
                (values["workspace_id"], values["idempotency_key"]),
            ).fetchone()
            if existing:
                return dict(existing), False
            cursor = conn.execute(
                """INSERT INTO notifications
                   (workspace_id,user_id,type,title,message,idempotency_key,delivery_status,created_at,delivered_at)
                   VALUES (?,?,?,?,?,?,'CREATED',?,NULL)""",
                (
                    values["workspace_id"],
                    values.get("user_id"),
                    values["type"],
                    values["title"],
                    values["message"],
                    values["idempotency_key"],
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM notifications WHERE id=?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row), True

    def list_notifications(self, workspace_id: int, user_id: int) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT * FROM notifications WHERE workspace_id=? AND (user_id IS NULL OR user_id=?)
                   ORDER BY created_at DESC LIMIT 100""",
                (workspace_id, user_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_notification(self, notification_id: int, workspace_id: int) -> dict:
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT * FROM notifications WHERE id=? AND workspace_id=?",
                (notification_id, workspace_id),
            ).fetchone()
            return dict(row) if row else {}

    def mark_notification_read(
        self, notification_id: int, workspace_id: int, user_id: int
    ) -> bool:
        with connection(self.database_path) as conn:
            return (
                conn.execute(
                    """UPDATE notifications SET is_read=1 WHERE id=? AND workspace_id=?
                   AND (user_id IS NULL OR user_id=?)""",
                    (notification_id, workspace_id, user_id),
                ).rowcount
                > 0
            )

    def create_export(self, values: dict) -> dict:
        now = now_iso()
        with connection(self.database_path) as conn:
            conn.execute(
                """INSERT INTO export_jobs
                   (id,workspace_id,created_by,format,export_type,parameters_json,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,'PENDING',?,?)""",
                (
                    values["id"],
                    values["workspace_id"],
                    values["created_by"],
                    values["format"],
                    values["export_type"],
                    json.dumps(values.get("parameters") or {}),
                    now,
                    now,
                ),
            )
            return self._export(conn, values["id"], values["workspace_id"])

    def create_background_job(
        self,
        *,
        job_id: str,
        workspace_id: int,
        job_type: str,
        resource_id: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> dict:
        now = now_iso()
        with connection(self.database_path) as conn:
            conn.execute(
                """INSERT INTO background_jobs
                   (id,workspace_id,job_type,resource_id,status,correlation_id,idempotency_key,
                    attempt_count,max_attempts,created_at,updated_at)
                   VALUES (?,?,?,?,'QUEUED',?,?,0,3,?,?)""",
                (
                    job_id,
                    workspace_id,
                    job_type,
                    resource_id,
                    correlation_id,
                    idempotency_key,
                    now,
                    now,
                ),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM background_jobs WHERE id=?", (job_id,)
                ).fetchone()
            )

    def begin_background_job(self, job_id: str) -> None:
        with connection(self.database_path) as conn:
            conn.execute(
                """UPDATE background_jobs SET status='RUNNING',attempt_count=attempt_count+1,
                   started_at=?,updated_at=? WHERE id=? AND status IN ('QUEUED','FAILED')""",
                (now_iso(), now_iso(), job_id),
            )

    def finish_background_job(
        self, job_id: str, status: str, error_summary: str | None = None
    ) -> None:
        now = now_iso()
        with connection(self.database_path) as conn:
            conn.execute(
                """UPDATE background_jobs SET status=?,error_summary=?,completed_at=?,updated_at=?
                   WHERE id=?""",
                (
                    status,
                    error_summary[:500] if error_summary else None,
                    now,
                    now,
                    job_id,
                ),
            )

    def deliver_notification(self, notification_id: int, workspace_id: int) -> None:
        with connection(self.database_path) as conn:
            conn.execute(
                """UPDATE notifications SET delivery_status='DELIVERED',delivered_at=?,
                   attempt_count=attempt_count+1 WHERE id=? AND workspace_id=?
                   AND delivery_status='CREATED'""",
                (now_iso(), notification_id, workspace_id),
            )

    def _export(self, conn, export_id: str, workspace_id: int) -> dict:
        row = conn.execute(
            "SELECT * FROM export_jobs WHERE id=? AND workspace_id=?",
            (export_id, workspace_id),
        ).fetchone()
        if not row:
            return {}
        item = dict(row)
        item["parameters"] = json.loads(item.pop("parameters_json"))
        return item

    def get_export(self, export_id: str, workspace_id: int) -> dict:
        with connection(self.database_path) as conn:
            return self._export(conn, export_id, workspace_id)

    def list_exports(self, workspace_id: int) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                "SELECT id FROM export_jobs WHERE workspace_id=? ORDER BY created_at DESC LIMIT 100",
                (workspace_id,),
            ).fetchall()
            return [self._export(conn, row["id"], workspace_id) for row in rows]

    def begin_export(self, export_id: str, workspace_id: int) -> None:
        with connection(self.database_path) as conn:
            conn.execute(
                "UPDATE export_jobs SET status='PROCESSING',updated_at=? WHERE id=? AND workspace_id=? AND status='PENDING'",
                (now_iso(), export_id, workspace_id),
            )

    def complete_export(
        self, export_id: str, workspace_id: int, stored_filename: str, row_count: int
    ) -> None:
        now = now_iso()
        with connection(self.database_path) as conn:
            conn.execute(
                """UPDATE export_jobs SET status='COMPLETED',stored_filename=?,object_key=?,row_count=?,completed_at=?,updated_at=?
                            WHERE id=? AND workspace_id=?""",
                (
                    stored_filename,
                    stored_filename,
                    row_count,
                    now,
                    now,
                    export_id,
                    workspace_id,
                ),
            )

    def fail_export(self, export_id: str, workspace_id: int, message: str) -> None:
        with connection(self.database_path) as conn:
            conn.execute(
                "UPDATE export_jobs SET status='FAILED',error_summary=?,updated_at=? WHERE id=? AND workspace_id=?",
                (message[:500], now_iso(), export_id, workspace_id),
            )

    def export_rows(self, workspace_id: int) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT event_id,user_id,session_id,event_name,occurred_at,revenue,source,device,region,product
                   FROM analytics_events WHERE workspace_id=? ORDER BY occurred_at,id""",
                (workspace_id,),
            ).fetchall()
            return [dict(row) for row in rows]
