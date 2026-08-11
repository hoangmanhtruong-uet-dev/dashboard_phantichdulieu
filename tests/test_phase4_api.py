import os
import tempfile
import unittest
import warnings
from pathlib import Path

warnings.simplefilter("ignore", ResourceWarning)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SEED_DEMO_DATA", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-thirty-two-characters")

from fastapi.testclient import TestClient  # noqa: E402

import ai_service  # noqa: E402
from data.database import connection  # noqa: E402


PASSWORD = "StrongPassword12!"


class Phase4ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self.temp_dir.name) / "sales.db"
        ai_service.DB_FILE = self.database_path
        self.context = TestClient(ai_service.app)
        self.client = self.context.__enter__()
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": "phase4-owner@example.com",
                "password": PASSWORD,
                "full_name": "Phase Four Owner",
                "workspace_name": "Phase Four",
            },
        )
        self.assertEqual(201, response.status_code, response.text)
        self.workspace_id = response.json()["data"]["workspace"]["id"]

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def csrf(self, client=None):
        active = client or self.client
        return {"X-CSRF-Token": active.cookies.get("nexus_csrf_token")}

    def test_report_pagination_search_filter_and_sort(self):
        with connection(self.database_path) as conn:
            conn.executemany(
                "INSERT INTO reports (workspace_id,name,report_type,status,updated_at) VALUES (?,?,?,?,?)",
                [
                    (
                        self.workspace_id,
                        f"Alpha {index:02d}",
                        "performance" if index % 2 else "custom",
                        "draft" if index % 2 else "ready",
                        f"2026-08-{index % 9 + 1:02d}T09:00:00",
                    )
                    for index in range(25)
                ],
            )
        response = self.client.get(
            "/api/reports?page=2&page_size=10&search=Alpha&sort_by=name&sort_order=asc"
        )
        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        self.assertEqual("Alpha 10", payload["data"][0]["name"])
        self.assertEqual(
            {"page": 2, "page_size": 10, "total": 25, "total_pages": 3},
            payload["meta"]["pagination"],
        )
        filtered = self.client.get(
            "/api/reports?search=Alpha&status=draft&sort_by=name&sort_order=desc"
        ).json()
        self.assertEqual(12, filtered["meta"]["pagination"]["total"])
        self.assertTrue(all(item["status"] == "draft" for item in filtered["data"]))

    def test_literal_search_wildcards_are_not_sql_wildcards(self):
        created = self.client.post(
            "/api/reports",
            headers=self.csrf(),
            json={"name": "100% Real_Report", "report_type": "custom"},
        )
        self.assertEqual(201, created.status_code, created.text)
        percent = self.client.get("/api/reports?search=100%25").json()
        underscore = self.client.get("/api/reports?search=Real_Report").json()
        self.assertEqual(1, percent["meta"]["pagination"]["total"])
        self.assertEqual(1, underscore["meta"]["pagination"]["total"])

    def test_custom_date_range_and_invalid_range(self):
        valid = self.client.get(
            "/api/dashboard/overview?date_from=2026-08-01&date_to=2026-08-31"
        )
        self.assertEqual(200, valid.status_code, valid.text)
        self.assertEqual("2026-08-01", valid.json()["data"]["period"]["from"])
        invalid = self.client.get(
            "/api/dashboard/overview?date_from=2026-08-31&date_to=2026-08-01"
        )
        self.assertEqual(400, invalid.status_code, invalid.text)
        incomplete = self.client.get(
            "/api/dashboard/overview?date_from=2026-08-01"
        )
        self.assertEqual(400, incomplete.status_code, incomplete.text)

    def test_profile_conflict_is_409(self):
        other_context = TestClient(ai_service.app)
        other = other_context.__enter__()
        self.addCleanup(other_context.__exit__, None, None, None)
        registered = other.post(
            "/api/auth/register",
            json={
                "email": "already-used@example.com",
                "password": PASSWORD,
                "full_name": "Other",
                "workspace_name": "Other Workspace",
            },
        )
        self.assertEqual(201, registered.status_code, registered.text)
        conflict = self.client.put(
            "/api/profile",
            headers=self.csrf(),
            json={
                "full_name": "Phase Four Owner",
                "job_title": "Owner",
                "email": "already-used@example.com",
                "phone": "",
                "workspace": "Phase Four",
            },
        )
        self.assertEqual(409, conflict.status_code, conflict.text)

    def test_list_validation_and_unauthenticated_access(self):
        self.assertEqual(422, self.client.get("/api/reports?page_size=0").status_code)
        anonymous_context = TestClient(ai_service.app)
        anonymous = anonymous_context.__enter__()
        self.addCleanup(anonymous_context.__exit__, None, None, None)
        self.assertEqual(401, anonymous.get("/api/reports?page=1").status_code)

    def test_phase4_frontend_assets_are_served(self):
        for path in (
            "/frontend/resource-state.js",
            "/frontend/api-client.js",
            "/frontend/resource-state.css",
        ):
            response = self.client.get(path)
            self.assertEqual(200, response.status_code, path)


if __name__ == "__main__":
    unittest.main()
