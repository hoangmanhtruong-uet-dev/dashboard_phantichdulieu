import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SEED_DEMO_DATA", "false")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-thirty-two-characters")

from fastapi.testclient import TestClient  # noqa: E402

import ai_service  # noqa: E402
from backend.operations.middleware import SlidingWindowLimiter  # noqa: E402
from data.database import connection  # noqa: E402


PASSWORD = "StrongPassword12!"


class Phase56ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self.temp.name) / "nexus.db"
        ai_service.DB_FILE = self.database_path
        self.context = TestClient(ai_service.app)
        self.client = self.context.__enter__()
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": "owner56@example.com",
                "password": PASSWORD,
                "full_name": "Owner 56",
                "workspace_name": "Phase 56",
            },
        )
        self.assertEqual(201, response.status_code, response.text)
        self.workspace_id = response.json()["data"]["workspace"]["id"]
        self.user_id = response.json()["data"]["user"]["id"]
        self._seed_events()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.temp.cleanup()

    def csrf(self):
        return {"X-CSRF-Token": self.client.cookies.get("nexus_csrf_token")}

    def _seed_events(self):
        rows = []
        for event_id, user, session, name, timestamp, revenue in [
            ("u1-signup", "u1", None, "signup", "2026-01-05T09:00:00+00:00", 0),
            ("u2-signup", "u2", None, "signup", "2026-01-05T09:00:00+00:00", 0),
            ("u1-view", "u1", "s1", "view_product", "2026-01-06T10:00:00+00:00", 0),
            ("u1-cart", "u1", "s1", "add_to_cart", "2026-01-06T10:01:00+00:00", 0),
            (
                "u1-checkout",
                "u1",
                "s1",
                "begin_checkout",
                "2026-01-06T10:02:00+00:00",
                0,
            ),
            ("u1-buy", "u1", "s1", "purchase", "2026-01-06T10:03:00+00:00", 100),
            ("u2-view", "u2", "s2", "view_product", "2026-01-06T11:00:00+00:00", 0),
            ("u2-buy", "u2", "s2", "purchase", "2026-01-06T11:02:00+00:00", 50),
            ("u1-d7", "u1", "s3", "view_product", "2026-01-12T10:00:00+00:00", 0),
        ]:
            rows.append(
                (
                    self.workspace_id,
                    event_id,
                    user,
                    session,
                    name,
                    timestamp,
                    revenue,
                    "organic",
                    "mobile",
                    "VN",
                    "Pro",
                )
            )
        with connection(self.database_path) as conn:
            conn.executemany(
                """INSERT INTO analytics_events
                (workspace_id,event_id,user_id,session_id,event_name,occurred_at,revenue,source,device,region,product)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )

    def test_real_analytics_endpoints_match_known_values(self):
        revenue = self.client.get(
            "/api/analytics/revenue?date_from=2026-01-05&date_to=2026-01-12"
        )
        self.assertEqual(200, revenue.status_code, revenue.text)
        self.assertEqual(150.0, revenue.json()["data"]["metrics"]["revenue"])
        self.assertEqual(75.0, revenue.json()["data"]["metrics"]["aov"])
        funnel = self.client.get(
            "/api/analytics/funnel?date_from=2026-01-05&date_to=2026-01-12"
        )
        self.assertEqual(3, funnel.json()["data"]["entered"])
        self.assertEqual(1, funnel.json()["data"]["completed"])
        retention = self.client.get("/api/analytics/retention").json()["data"]
        self.assertEqual(100.0, retention["periods"][0]["retention_rate"])
        self.assertEqual(50.0, retention["periods"][1]["retention_rate"])
        self.assertEqual(2, retention["periods"][1]["eligible_users"])
        cohort = self.client.get("/api/analytics/cohort").json()["data"]
        self.assertEqual([100.0, 50.0], cohort["cohorts"][0]["retention"][:2])

    def test_segment_is_server_validated_and_workspace_scoped(self):
        response = self.client.post(
            "/api/analytics/segments",
            headers=self.csrf(),
            json={
                "name": "High value",
                "match_type": "ALL",
                "rules": [{"field": "revenue", "operator": "gte", "value": 100}],
            },
        )
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(1, response.json()["data"]["preview"]["user_count"])
        arbitrary = self.client.post(
            "/api/analytics/segments/preview",
            headers=self.csrf(),
            json={
                "match_type": "ALL",
                "rules": [
                    {
                        "field": "workspace_id",
                        "operator": "eq",
                        "value": self.workspace_id,
                    }
                ],
            },
        )
        self.assertEqual(422, arbitrary.status_code)
        other_context = TestClient(ai_service.app)
        other = other_context.__enter__()
        self.addCleanup(other_context.__exit__, None, None, None)
        registered = other.post(
            "/api/auth/register",
            json={
                "email": "other56@example.com",
                "password": PASSWORD,
                "full_name": "Other",
                "workspace_name": "Other",
            },
        )
        self.assertEqual(201, registered.status_code)
        self.assertEqual([], other.get("/api/analytics/segments").json()["data"])
        self.assertEqual(
            0.0,
            other.get(
                "/api/analytics/revenue?date_from=2026-01-01&date_to=2026-01-31"
            ).json()["data"]["metrics"]["revenue"],
        )

    def test_notifications_are_idempotent_and_audited(self):
        payload = {
            "type": "IMPORT",
            "title": "Import complete",
            "message": "Dataset is ready",
            "idempotency_key": "import-job-123",
        }
        first = self.client.post(
            "/api/notifications", headers=self.csrf(), json=payload
        )
        second = self.client.post(
            "/api/notifications", headers=self.csrf(), json=payload
        )
        self.assertTrue(first.json()["data"]["created"])
        self.assertFalse(second.json()["data"]["created"])
        self.assertEqual(first.json()["data"]["id"], second.json()["data"]["id"])
        audit = self.client.get("/api/audit-logs").json()["data"]
        self.assertGreaterEqual(len(audit), 2)
        self.assertNotIn("message", audit[0]["metadata"])

    def test_real_exports_and_workspace_authorization(self):
        first_export_id = None
        for file_format, content_type in [
            ("CSV", "text/csv"),
            (
                "XLSX",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("PDF", "application/pdf"),
        ]:
            created = self.client.post(
                "/api/exports",
                headers=self.csrf(),
                json={"format": file_format, "export_type": "ANALYTICS_EVENTS"},
            )
            self.assertEqual(202, created.status_code, created.text)
            export_id = created.json()["data"]["id"]
            first_export_id = first_export_id or export_id
            status = self.client.get(f"/api/exports/{export_id}").json()["data"]
            self.assertEqual("COMPLETED", status["status"], status)
            self.assertEqual(9, status["row_count"])
            downloaded = self.client.get(f"/api/exports/{export_id}/download")
            self.assertEqual(200, downloaded.status_code, downloaded.text[:200])
            self.assertTrue(downloaded.headers["content-type"].startswith(content_type))
        other_context = TestClient(ai_service.app)
        other = other_context.__enter__()
        self.addCleanup(other_context.__exit__, None, None, None)
        registered = other.post(
            "/api/auth/register",
            json={
                "email": "export-other@example.com",
                "password": PASSWORD,
                "full_name": "Export Other",
                "workspace_name": "Export Other",
            },
        )
        self.assertEqual(201, registered.status_code)
        self.assertEqual(404, other.get(f"/api/exports/{first_export_id}").status_code)
        self.assertEqual(
            404,
            other.get(f"/api/exports/{first_export_id}/download").status_code,
        )

    def test_operational_endpoints_and_security_headers(self):
        health = self.client.get("/health")
        ready = self.client.get("/ready")
        metrics = self.client.get("/metrics")
        self.assertEqual(200, health.status_code)
        self.assertEqual(200, ready.status_code)
        self.assertIn("nexus_http_requests_total", metrics.text)
        self.assertTrue(health.headers.get("x-request-id"))
        self.assertEqual("nosniff", health.headers["x-content-type-options"])
        self.assertIn("default-src 'self'", health.headers["content-security-policy"])

    def test_viewer_cannot_create_exports_or_notifications(self):
        with connection(self.database_path) as conn:
            conn.execute(
                "UPDATE workspace_members SET role='VIEWER' WHERE workspace_id=? AND user_id=?",
                (self.workspace_id, self.user_id),
            )
        export = self.client.post(
            "/api/exports",
            headers=self.csrf(),
            json={"format": "CSV", "export_type": "ANALYTICS_EVENTS"},
        )
        notification = self.client.post(
            "/api/notifications",
            headers=self.csrf(),
            json={
                "type": "TEST",
                "title": "Denied",
                "message": "Denied",
                "idempotency_key": "viewer-denied-1",
            },
        )
        self.assertEqual(403, export.status_code)
        self.assertEqual(403, notification.status_code)
        self.assertEqual(200, self.client.get("/api/analytics/retention").status_code)

    def test_sensitive_endpoint_limiter_rejects_excess(self):
        limiter = SlidingWindowLimiter()
        self.assertTrue(limiter.allow("upload:client", 2))
        self.assertTrue(limiter.allow("upload:client", 2))
        self.assertFalse(limiter.allow("upload:client", 2))


if __name__ == "__main__":
    unittest.main()
