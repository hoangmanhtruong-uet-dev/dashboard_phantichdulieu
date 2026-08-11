import os
import tempfile
import unittest
import warnings
from datetime import timedelta
from pathlib import Path

import jwt

# Starlette 0.37's TestClient on Python 3.13 emits late anyio stream cleanup warnings.
warnings.simplefilter("ignore", ResourceWarning)

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SEED_DEMO_DATA", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-thirty-two-characters")

from fastapi.testclient import TestClient  # noqa: E402

import ai_service  # noqa: E402
from backend.auth.security import ACCESS_COOKIE, REFRESH_COOKIE, to_iso, utc_now  # noqa: E402
from backend.config import settings  # noqa: E402
from data.database import connection  # noqa: E402
from data.migrate import migration_status  # noqa: E402


PASSWORD = "StrongPassword12!"


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self.temp_dir.name) / "sales.db"
        ai_service.DB_FILE = self.database_path
        self.client_context = TestClient(ai_service.app)
        self.client = self.client_context.__enter__()
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": "owner@example.com",
                "password": PASSWORD,
                "full_name": "Owner User",
                "workspace_name": "Owner Workspace",
            },
        )
        self.assertEqual(201, response.status_code, response.text)
        self.owner_workspace_id = response.json()["data"]["workspace"]["id"]

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def csrf(self, client=None):
        active = client or self.client
        return {"X-CSRF-Token": active.cookies.get("nexus_csrf_token")}

    def new_client(self) -> TestClient:
        context = TestClient(ai_service.app)
        client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return client

    def create_member(self, email: str, role: str) -> tuple[TestClient, int]:
        client = self.new_client()
        response = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "full_name": role.title(),
                "workspace_name": f"{role} Personal",
            },
        )
        self.assertEqual(201, response.status_code, response.text)
        user_id = response.json()["data"]["user"]["id"]
        now = to_iso(utc_now())
        with connection(self.database_path) as conn:
            conn.execute(
                "INSERT INTO workspace_members (workspace_id,user_id,role,joined_at) VALUES (?,?,?,?)",
                (self.owner_workspace_id, user_id, role, now),
            )
            session_id = conn.execute(
                "SELECT id FROM auth_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()["id"]
            conn.execute(
                "UPDATE auth_sessions SET active_workspace_id=? WHERE id=?",
                (self.owner_workspace_id, session_id),
            )
        return client, user_id

    def test_migrations_are_current(self):
        status = migration_status(self.database_path)
        self.assertTrue(status["current"])
        self.assertEqual(["001", "002", "003", "004"], status["applied"])

    def test_register_login_and_incorrect_password(self):
        other = self.new_client()
        wrong = other.post(
            "/api/auth/login", json={"email": "owner@example.com", "password": "wrong"}
        )
        self.assertEqual(401, wrong.status_code)
        good = other.post(
            "/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
        )
        self.assertEqual(200, good.status_code)
        self.assertIn("HttpOnly", good.headers.get("set-cookie", ""))
        self.assertEqual(200, other.get("/api/auth/session").status_code)

    def test_unauthenticated_api_is_denied(self):
        anonymous = self.new_client()
        for path in ("/api/bootstrap", "/api/reports", "/api/workspaces"):
            self.assertEqual(401, anonymous.get(path).status_code)

    def test_expired_access_token_is_denied(self):
        payload = {
            "sub": "1",
            "sid": "expired",
            "typ": "access",
            "iat": utc_now() - timedelta(hours=2),
            "exp": utc_now() - timedelta(hours=1),
        }
        expired = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        anonymous = self.new_client()
        anonymous.cookies.set(ACCESS_COOKIE, expired)
        self.assertEqual(401, anonymous.get("/api/auth/session").status_code)

    def test_refresh_rotation_and_reuse_revokes_family(self):
        old_refresh = self.client.cookies.get(REFRESH_COOKIE)
        first = self.client.post("/api/auth/refresh", headers=self.csrf())
        self.assertEqual(200, first.status_code)
        new_refresh = self.client.cookies.get(REFRESH_COOKIE)
        self.assertNotEqual(old_refresh, new_refresh)
        replay = self.new_client()
        replay.cookies.set(REFRESH_COOKIE, old_refresh)
        replay.cookies.set("nexus_csrf_token", "csrf")
        self.assertEqual(
            401,
            replay.post(
                "/api/auth/refresh", headers={"X-CSRF-Token": "csrf"}
            ).status_code,
        )
        replay.cookies.set(REFRESH_COOKIE, new_refresh)
        self.assertEqual(
            401,
            replay.post(
                "/api/auth/refresh", headers={"X-CSRF-Token": "csrf"}
            ).status_code,
        )

    def test_logout_revokes_session(self):
        access = self.client.cookies.get(ACCESS_COOKIE)
        self.assertEqual(
            200, self.client.post("/api/auth/logout", headers=self.csrf()).status_code
        )
        anonymous = self.new_client()
        anonymous.cookies.set(ACCESS_COOKIE, access)
        self.assertEqual(401, anonymous.get("/api/auth/session").status_code)

    def test_password_reset_is_generic_and_invalidates_sessions(self):
        response = self.client.post(
            "/api/auth/forgot-password", json={"email": "owner@example.com"}
        )
        token = response.json()["meta"]["reset_token"]
        reset = self.client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "NewStrongPassword13!"},
        )
        self.assertEqual(200, reset.status_code)
        self.assertEqual(401, self.client.get("/api/auth/session").status_code)
        missing = self.new_client().post(
            "/api/auth/forgot-password", json={"email": "missing@example.com"}
        )
        self.assertEqual(
            response.json()["data"]["message"], missing.json()["data"]["message"]
        )

    def test_rbac_viewer_and_analyst_boundaries(self):
        viewer, _ = self.create_member("viewer@example.com", "VIEWER")
        self.assertEqual(200, viewer.get("/api/reports").status_code)
        self.assertEqual(
            403,
            viewer.post(
                "/api/reports",
                headers=self.csrf(viewer),
                json={"name": "No", "report_type": "custom"},
            ).status_code,
        )
        analyst, analyst_id = self.create_member("analyst@example.com", "ANALYST")
        self.assertEqual(
            201,
            analyst.post(
                "/api/reports",
                headers=self.csrf(analyst),
                json={"name": "Allowed", "report_type": "custom"},
            ).status_code,
        )
        self.assertEqual(
            403,
            analyst.patch(
                f"/api/workspaces/current/members/{analyst_id}",
                headers=self.csrf(analyst),
                json={"role": "ADMIN"},
            ).status_code,
        )

    def test_cross_workspace_resource_and_switch_are_denied(self):
        created = self.client.post(
            "/api/alerts",
            headers=self.csrf(),
            json={"title": "Private", "description": "Workspace A", "severity": "low"},
        )
        alert_id = created.json()["data"]["id"]
        other = self.new_client()
        registration = other.post(
            "/api/auth/register",
            json={
                "email": "other@example.com",
                "password": PASSWORD,
                "full_name": "Other Owner",
                "workspace_name": "Workspace B",
            },
        )
        self.assertEqual(201, registration.status_code)
        self.assertEqual(
            404,
            other.patch(
                f"/api/alerts/{alert_id}/read", headers=self.csrf(other)
            ).status_code,
        )
        workspace_b = registration.json()["data"]["workspace"]["id"]
        self.assertEqual(
            403,
            self.client.post(
                "/api/workspaces/switch",
                headers=self.csrf(),
                json={"workspace_id": workspace_b},
            ).status_code,
        )

    def test_invitation_flow_and_server_side_member_guard(self):
        invitee = self.new_client()
        registration = invitee.post(
            "/api/auth/register",
            json={
                "email": "invitee@example.com",
                "password": PASSWORD,
                "full_name": "Invitee",
                "workspace_name": "Invitee Personal",
            },
        )
        self.assertEqual(201, registration.status_code)
        invitation = self.client.post(
            "/api/workspaces/current/invitations",
            headers=self.csrf(),
            json={"email": "invitee@example.com", "role": "ANALYST"},
        )
        self.assertEqual(201, invitation.status_code)
        token = invitation.json()["data"]["invitation_token"]
        accepted = invitee.post(
            "/api/workspaces/invitations/accept",
            headers=self.csrf(invitee),
            json={"token": token},
        )
        self.assertEqual(200, accepted.status_code)

    def test_protected_endpoints_and_csrf(self):
        self.assertEqual(
            403,
            self.client.post(
                "/api/reports", json={"name": "Missing CSRF", "report_type": "custom"}
            ).status_code,
        )
        for path in (
            "/api/bootstrap",
            "/api/dashboard/overview",
            "/api/analytics/revenue",
            "/api/insights",
            "/api/alerts",
            "/api/reports",
            "/api/data-sources",
            "/api/saved-views",
            "/api/profile",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(200, response.status_code, response.text)
                self.assertTrue(response.json()["success"])


if __name__ == "__main__":
    unittest.main()
