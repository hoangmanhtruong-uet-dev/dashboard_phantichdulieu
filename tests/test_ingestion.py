import io
import os
import tempfile
import unittest
import warnings
from pathlib import Path

from openpyxl import Workbook

warnings.simplefilter("ignore", ResourceWarning)

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SEED_DEMO_DATA", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-thirty-two-characters")

from fastapi.testclient import TestClient  # noqa: E402

import ai_service  # noqa: E402
from backend.auth.security import to_iso, utc_now  # noqa: E402
from backend.config import settings  # noqa: E402
from data.database import connection  # noqa: E402


PASSWORD = "StrongPassword12!"
VALID_CSV = (
    b"created_at,amount,order_id,customer_id,category,region\n"
    b"2026-08-01T10:00:00Z,125.50,ORD-1,CUST-1,Software,APAC\n"
    b"2026-08-02T11:30:00Z,80,ORD-2,CUST-2,Services,EMEA\n"
)
MAPPING = [
    {
        "source_column": "created_at",
        "canonical_field": "timestamp",
        "data_type": "DATE_TIME",
    },
    {
        "source_column": "amount",
        "canonical_field": "revenue",
        "data_type": "NUMBER",
    },
    {
        "source_column": "order_id",
        "canonical_field": "event_id",
        "data_type": "STRING",
    },
    {
        "source_column": "customer_id",
        "canonical_field": "customer_id",
        "data_type": "STRING",
    },
    {
        "source_column": "category",
        "canonical_field": "category",
        "data_type": "STRING",
    },
    {
        "source_column": "region",
        "canonical_field": "region",
        "data_type": "STRING",
    },
]


class IngestionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self.temp_dir.name) / "sales.db"
        ai_service.DB_FILE = self.database_path
        self.client_context = TestClient(ai_service.app)
        self.client = self.client_context.__enter__()
        registration = self.client.post(
            "/api/auth/register",
            json={
                "email": "ingestion-owner@example.com",
                "password": PASSWORD,
                "full_name": "Ingestion Owner",
                "workspace_name": "Ingestion Workspace",
            },
        )
        self.assertEqual(201, registration.status_code, registration.text)
        self.workspace_id = registration.json()["data"]["workspace"]["id"]

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def csrf(self, client=None):
        active = client or self.client
        return {"X-CSRF-Token": active.cookies.get("nexus_csrf_token")}

    def new_client(self):
        context = TestClient(ai_service.app)
        client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return client

    def upload(self, content, filename="orders.csv", mime="text/csv", client=None):
        active = client or self.client
        return active.post(
            "/api/ingestion/uploads",
            headers=self.csrf(active),
            files={"file": (filename, content, mime)},
        )

    def preview(self, job_id, sheet_name=None, client=None):
        active = client or self.client
        return active.post(
            f"/api/ingestion/jobs/{job_id}/preview",
            headers=self.csrf(active),
            json={"sheet_name": sheet_name},
        )

    def run_import(self, job_id, *, allow_partial=False, mapping=None, client=None):
        active = client or self.client
        return active.post(
            f"/api/ingestion/jobs/{job_id}/import",
            headers=self.csrf(active),
            json={
                "display_name": "Orders import",
                "allow_partial": allow_partial,
                "fields": mapping or MAPPING,
            },
        )

    def upload_and_preview(self, content=VALID_CSV, **upload_options):
        uploaded = self.upload(content, **upload_options)
        self.assertEqual(201, uploaded.status_code, uploaded.text)
        job_id = uploaded.json()["data"]["job"]["id"]
        previewed = self.preview(job_id)
        self.assertEqual(200, previewed.status_code, previewed.text)
        return job_id, previewed.json()["data"]

    @staticmethod
    def xlsx_bytes():
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Orders"
        sheet.append(
            ["created_at", "amount", "order_id", "customer_id", "category", "region"]
        )
        sheet.append(
            ["2026-08-01T10:00:00Z", 125.5, "XLSX-1", "C-1", "Software", "APAC"]
        )
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()

    def register_other_owner(self):
        other = self.new_client()
        response = other.post(
            "/api/auth/register",
            json={
                "email": "other-ingestion-owner@example.com",
                "password": PASSWORD,
                "full_name": "Other Owner",
                "workspace_name": "Other Workspace",
            },
        )
        self.assertEqual(201, response.status_code, response.text)
        return other

    def create_viewer(self):
        viewer = self.new_client()
        registered = viewer.post(
            "/api/auth/register",
            json={
                "email": "ingestion-viewer@example.com",
                "password": PASSWORD,
                "full_name": "Viewer",
                "workspace_name": "Viewer Personal",
            },
        )
        self.assertEqual(201, registered.status_code, registered.text)
        user_id = registered.json()["data"]["user"]["id"]
        with connection(self.database_path) as conn:
            conn.execute(
                "INSERT INTO workspace_members (workspace_id,user_id,role,joined_at) VALUES (?,?,?,?)",
                (self.workspace_id, user_id, "VIEWER", to_iso(utc_now())),
            )
            session_id = conn.execute(
                "SELECT id FROM auth_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()["id"]
            conn.execute(
                "UPDATE auth_sessions SET active_workspace_id=? WHERE id=?",
                (self.workspace_id, session_id),
            )
        return viewer

    def test_valid_csv_preview_and_successful_import(self):
        job_id, preview = self.upload_and_preview()
        self.assertEqual("PREVIEWED", preview["job"]["status"])
        self.assertEqual(2, preview["preview"]["row_count"])
        self.assertEqual("created_at", preview["preview"]["columns"][0])

        imported = self.run_import(job_id)
        self.assertEqual(200, imported.status_code, imported.text)
        result = imported.json()["data"]
        self.assertEqual("COMPLETED", result["job"]["status"])
        self.assertEqual(2, result["job"]["valid_rows"])
        self.assertEqual(0, result["job"]["invalid_rows"])
        self.assertEqual("FILE_UPLOAD", result["data_source"]["source_type"])
        with connection(self.database_path) as conn:
            self.assertEqual(
                2,
                conn.execute(
                    "SELECT COUNT(*) FROM raw_import_records WHERE job_id=?",
                    (job_id,),
                ).fetchone()[0],
            )
            self.assertEqual(
                2,
                conn.execute(
                    "SELECT COUNT(*) FROM orders WHERE import_job_id=?", (job_id,)
                ).fetchone()[0],
            )

    def test_valid_xlsx_preview_and_import(self):
        job_id, preview = self.upload_and_preview(
            self.xlsx_bytes(),
            filename="orders.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(["Orders"], preview["preview"]["sheet_names"])
        imported = self.run_import(job_id)
        self.assertEqual(200, imported.status_code, imported.text)
        self.assertEqual("COMPLETED", imported.json()["data"]["job"]["status"])

    def test_rejects_malformed_empty_oversized_and_wrong_extension(self):
        malformed = self.upload(b'created_at,amount\n"unterminated,10\n')
        self.assertEqual(201, malformed.status_code, malformed.text)
        job_id = malformed.json()["data"]["job"]["id"]
        failed_preview = self.preview(job_id)
        self.assertEqual(422, failed_preview.status_code, failed_preview.text)
        self.assertEqual("MALFORMED_CSV", failed_preview.json()["error"]["code"])
        job = self.client.get(f"/api/ingestion/jobs/{job_id}")
        self.assertEqual("FAILED", job.json()["data"]["status"])

        empty = self.upload(b"")
        self.assertEqual(422, empty.status_code, empty.text)
        self.assertEqual("EMPTY_FILE", empty.json()["error"]["code"])

        oversized = self.upload(b"x" * (settings.max_upload_bytes + 1))
        self.assertEqual(413, oversized.status_code, oversized.text)
        self.assertEqual("FILE_TOO_LARGE", oversized.json()["error"]["code"])

        wrong = self.upload(VALID_CSV, filename="orders.txt", mime="text/plain")
        self.assertEqual(415, wrong.status_code, wrong.text)
        self.assertEqual("UNSUPPORTED_EXTENSION", wrong.json()["error"]["code"])

    def test_invalid_values_mapping_error_and_failed_state(self):
        invalid = (
            b"created_at,amount,order_id,customer_id,category,region\n"
            b"not-a-date,not-a-number,BAD-1,C-1,Software,APAC\n"
        )
        job_id, _ = self.upload_and_preview(invalid)
        mapping_error = self.run_import(job_id, mapping=MAPPING[1:])
        self.assertEqual(422, mapping_error.status_code, mapping_error.text)
        self.assertEqual(
            "MISSING_REQUIRED_MAPPING", mapping_error.json()["error"]["code"]
        )

        failed = self.run_import(job_id)
        self.assertEqual(200, failed.status_code, failed.text)
        self.assertEqual("FAILED", failed.json()["data"]["job"]["status"])
        errors = self.client.get(f"/api/ingestion/jobs/{job_id}/errors")
        codes = {item["code"] for item in errors.json()["data"]["items"]}
        self.assertEqual({"INVALID_DATE", "INVALID_NUMBER"}, codes)

    def test_partial_validation_errors_can_complete(self):
        partial = (
            b"created_at,amount,order_id,customer_id,category,region\n"
            b"2026-08-01T10:00:00Z,10,OK-1,C-1,Software,APAC\n"
            b"bad-date,nope,BAD-1,C-2,Services,EMEA\n"
        )
        job_id, _ = self.upload_and_preview(partial)
        imported = self.run_import(job_id, allow_partial=True)
        self.assertEqual(200, imported.status_code, imported.text)
        job = imported.json()["data"]["job"]
        self.assertEqual("COMPLETED", job["status"])
        self.assertEqual(1, job["valid_rows"])
        self.assertEqual(1, job["invalid_rows"])

    def test_duplicate_import_is_prevented_by_workspace_and_hash(self):
        job_id, _ = self.upload_and_preview()
        self.assertEqual(
            "COMPLETED", self.run_import(job_id).json()["data"]["job"]["status"]
        )
        duplicate = self.upload(VALID_CSV, filename="renamed.csv")
        self.assertEqual(409, duplicate.status_code, duplicate.text)
        self.assertEqual("DUPLICATE_IMPORT", duplicate.json()["error"]["code"])

    def test_unauthorized_upload_and_cross_workspace_access_are_denied(self):
        anonymous = self.new_client()
        denied = anonymous.post(
            "/api/ingestion/uploads",
            files={"file": ("orders.csv", VALID_CSV, "text/csv")},
        )
        self.assertEqual(401, denied.status_code, denied.text)

        viewer = self.create_viewer()
        viewer_denied = self.upload(VALID_CSV, client=viewer)
        self.assertEqual(403, viewer_denied.status_code, viewer_denied.text)

        job_id, _ = self.upload_and_preview()
        other = self.register_other_owner()
        hidden = other.get(f"/api/ingestion/jobs/{job_id}")
        self.assertEqual(404, hidden.status_code, hidden.text)

    def test_import_history_and_failure_inspection_are_workspace_scoped(self):
        job_id, _ = self.upload_and_preview()
        imported = self.run_import(job_id)
        source_id = imported.json()["data"]["data_source"]["id"]
        history = self.client.get(f"/api/ingestion/sources/{source_id}/history")
        self.assertEqual(200, history.status_code, history.text)
        self.assertEqual(job_id, history.json()["data"]["items"][0]["id"])

        other = self.register_other_owner()
        hidden = other.get(f"/api/ingestion/sources/{source_id}/history")
        self.assertEqual(404, hidden.status_code, hidden.text)


if __name__ == "__main__":
    unittest.main()
