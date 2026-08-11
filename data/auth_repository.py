import re
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Optional

from backend.auth.security import hash_token, new_token, to_iso, utc_now
from backend.config import settings
from data.database import connection


class AuthRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def find_user_by_email(self, email: str) -> Optional[dict]:
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email=? COLLATE NOCASE",
                (email.strip().lower(),),
            ).fetchone()
            return dict(row) if row else None

    def find_user(self, user_id: int) -> Optional[dict]:
        with connection(self.database_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def _unique_slug(self, conn, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
        slug = base
        counter = 2
        while conn.execute("SELECT 1 FROM workspaces WHERE slug=?", (slug,)).fetchone():
            slug, counter = f"{base}-{counter}", counter + 1
        return slug

    def register_owner(
        self, email: str, full_name: str, password_hash: str, workspace_name: str
    ) -> tuple[dict, dict]:
        now = to_iso(utc_now())
        with connection(self.database_path) as conn:
            cursor = conn.execute(
                "INSERT INTO users (email,full_name,password_hash,created_at,updated_at) VALUES (?,?,?,?,?)",
                (email.strip().lower(), full_name, password_hash, now, now),
            )
            user_id = cursor.lastrowid
            workspace_cursor = conn.execute(
                "INSERT INTO workspaces (name,slug,created_by,created_at) VALUES (?,?,?,?)",
                (workspace_name, self._unique_slug(conn, workspace_name), user_id, now),
            )
            workspace_id = workspace_cursor.lastrowid
            conn.execute(
                "INSERT INTO workspace_members (workspace_id,user_id,role,joined_at) VALUES (?,?,?,?)",
                (workspace_id, user_id, "OWNER", now),
            )
            # Preserve legacy demo records by assigning unowned rows only once.
            for table in (
                "orders",
                "insights",
                "alerts",
                "reports",
                "data_sources",
                "saved_views",
            ):
                conn.execute(
                    f"UPDATE {table} SET workspace_id=? WHERE workspace_id IS NULL",
                    (workspace_id,),
                )
            user = dict(
                conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            )
            workspace = dict(
                conn.execute(
                    "SELECT * FROM workspaces WHERE id=?", (workspace_id,)
                ).fetchone()
            )
            workspace["role"] = "OWNER"
            return user, workspace

    def memberships(self, user_id: int) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT w.id,w.name,w.slug,wm.role,wm.joined_at
                   FROM workspace_members wm JOIN workspaces w ON w.id=wm.workspace_id
                   WHERE wm.user_id=? ORDER BY w.name""",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def membership(self, user_id: int, workspace_id: int) -> Optional[dict]:
        with connection(self.database_path) as conn:
            row = conn.execute(
                """SELECT w.id,w.name,w.slug,wm.role FROM workspace_members wm
                   JOIN workspaces w ON w.id=wm.workspace_id WHERE wm.user_id=? AND wm.workspace_id=?""",
                (user_id, workspace_id),
            ).fetchone()
            return dict(row) if row else None

    def create_session(
        self, user_id: int, workspace_id: int, ip_address: str, user_agent: str
    ) -> tuple[str, str]:
        now = utc_now()
        session_id = secrets.token_urlsafe(32)
        family_id = secrets.token_urlsafe(24)
        refresh_id = secrets.token_urlsafe(24)
        refresh_token = new_token()
        session_expires = now + timedelta(days=settings.session_days)
        refresh_expires = now + timedelta(days=settings.refresh_token_days)
        with connection(self.database_path) as conn:
            conn.execute(
                "INSERT INTO auth_sessions (id,user_id,active_workspace_id,created_at,last_seen_at,expires_at,ip_address,user_agent) VALUES (?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    user_id,
                    workspace_id,
                    to_iso(now),
                    to_iso(now),
                    to_iso(session_expires),
                    ip_address[:64],
                    user_agent[:500],
                ),
            )
            conn.execute(
                "INSERT INTO refresh_tokens (id,session_id,family_id,token_hash,created_at,expires_at) VALUES (?,?,?,?,?,?)",
                (
                    refresh_id,
                    session_id,
                    family_id,
                    hash_token(refresh_token),
                    to_iso(now),
                    to_iso(refresh_expires),
                ),
            )
        return session_id, refresh_token

    def session_context(self, session_id: str, user_id: int) -> Optional[dict]:
        now = to_iso(utc_now())
        with connection(self.database_path) as conn:
            row = conn.execute(
                """SELECT s.id session_id,s.user_id,s.active_workspace_id workspace_id,u.email,u.full_name,u.job_title,u.phone,wm.role,w.name workspace_name,w.slug workspace_slug
                   FROM auth_sessions s JOIN users u ON u.id=s.user_id
                   JOIN workspace_members wm ON wm.user_id=s.user_id AND wm.workspace_id=s.active_workspace_id
                   JOIN workspaces w ON w.id=s.active_workspace_id
                   WHERE s.id=? AND s.user_id=? AND s.revoked_at IS NULL AND s.expires_at>? AND u.is_active=1""",
                (session_id, user_id, now),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE auth_sessions SET last_seen_at=? WHERE id=?",
                    (now, session_id),
                )
            return dict(row) if row else None

    def rotate_refresh(self, token: str) -> tuple[Optional[dict], Optional[str], str]:
        now = utc_now()
        token_digest = hash_token(token)
        with connection(self.database_path) as conn:
            row = conn.execute(
                """SELECT rt.*,s.user_id,s.active_workspace_id,s.revoked_at session_revoked,s.expires_at session_expires
                   FROM refresh_tokens rt JOIN auth_sessions s ON s.id=rt.session_id WHERE rt.token_hash=?""",
                (token_digest,),
            ).fetchone()
            if not row:
                return None, None, "invalid"
            record = dict(row)
            if record["revoked_at"]:
                revoked_at = to_iso(now)
                conn.execute(
                    "UPDATE refresh_tokens SET revoked_at=COALESCE(revoked_at,?) WHERE family_id=?",
                    (revoked_at, record["family_id"]),
                )
                conn.execute(
                    "UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE id=?",
                    (revoked_at, record["session_id"]),
                )
                return None, None, "reused"
            if (
                record["session_revoked"]
                or record["expires_at"] <= to_iso(now)
                or record["session_expires"] <= to_iso(now)
            ):
                return None, None, "expired"
            replacement = new_token()
            replacement_id = secrets.token_urlsafe(24)
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at=? WHERE id=?",
                (to_iso(now), record["id"]),
            )
            conn.execute(
                "INSERT INTO refresh_tokens (id,session_id,family_id,token_hash,rotated_from,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
                (
                    replacement_id,
                    record["session_id"],
                    record["family_id"],
                    hash_token(replacement),
                    record["id"],
                    to_iso(now),
                    record["expires_at"],
                ),
            )
            return record, replacement, "ok"

    def revoke_session(self, session_id: str) -> None:
        now = to_iso(utc_now())
        with connection(self.database_path) as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE id=?",
                (now, session_id),
            )
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at=COALESCE(revoked_at,?) WHERE session_id=?",
                (now, session_id),
            )

    def revoke_all_user_sessions(self, user_id: int) -> None:
        now = to_iso(utc_now())
        with connection(self.database_path) as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE user_id=?",
                (now, user_id),
            )
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at=COALESCE(revoked_at,?) WHERE session_id IN (SELECT id FROM auth_sessions WHERE user_id=?)",
                (now, user_id),
            )

    def switch_workspace(
        self, session_id: str, user_id: int, workspace_id: int
    ) -> bool:
        with connection(self.database_path) as conn:
            allowed = conn.execute(
                "SELECT 1 FROM workspace_members WHERE user_id=? AND workspace_id=?",
                (user_id, workspace_id),
            ).fetchone()
            if not allowed:
                return False
            conn.execute(
                "UPDATE auth_sessions SET active_workspace_id=? WHERE id=? AND user_id=? AND revoked_at IS NULL",
                (workspace_id, session_id, user_id),
            )
            return True

    def create_password_reset(self, user_id: int) -> str:
        now = utc_now()
        token = new_token()
        with connection(self.database_path) as conn:
            conn.execute(
                "UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",
                (to_iso(now), user_id),
            )
            conn.execute(
                "INSERT INTO password_reset_tokens (id,user_id,token_hash,created_at,expires_at) VALUES (?,?,?,?,?)",
                (
                    secrets.token_urlsafe(24),
                    user_id,
                    hash_token(token),
                    to_iso(now),
                    to_iso(now + timedelta(minutes=30)),
                ),
            )
        return token

    def consume_password_reset(self, token: str, password_hash: str) -> Optional[int]:
        now = to_iso(utc_now())
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT * FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL AND expires_at>?",
                (hash_token(token), now),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE password_reset_tokens SET used_at=? WHERE id=?",
                (now, row["id"]),
            )
            conn.execute(
                "UPDATE users SET password_hash=?,updated_at=? WHERE id=?",
                (password_hash, now, row["user_id"]),
            )
            conn.execute(
                "UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE user_id=?",
                (now, row["user_id"]),
            )
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at=COALESCE(revoked_at,?) WHERE session_id IN (SELECT id FROM auth_sessions WHERE user_id=?)",
                (now, row["user_id"]),
            )
            return int(row["user_id"])

    def list_members(self, workspace_id: int) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT u.id,u.email,u.full_name,u.job_title,wm.role,wm.joined_at
                   FROM workspace_members wm JOIN users u ON u.id=wm.user_id WHERE wm.workspace_id=? ORDER BY u.full_name""",
                (workspace_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def create_invitation(
        self, workspace_id: int, email: str, role: str, invited_by: int
    ) -> tuple[dict, str]:
        now = utc_now()
        token = new_token()
        with connection(self.database_path) as conn:
            member = conn.execute(
                "SELECT 1 FROM workspace_members wm JOIN users u ON u.id=wm.user_id WHERE wm.workspace_id=? AND u.email=? COLLATE NOCASE",
                (workspace_id, email),
            ).fetchone()
            if member:
                raise ValueError("User is already a member")
            conn.execute(
                "UPDATE invitations SET revoked_at=? WHERE workspace_id=? AND email=? COLLATE NOCASE AND accepted_at IS NULL AND revoked_at IS NULL",
                (to_iso(now), workspace_id, email),
            )
            cursor = conn.execute(
                "INSERT INTO invitations (workspace_id,email,role,token_hash,invited_by,expires_at,created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    workspace_id,
                    email.lower(),
                    role,
                    hash_token(token),
                    invited_by,
                    to_iso(now + timedelta(days=7)),
                    to_iso(now),
                ),
            )
            invite = dict(
                conn.execute(
                    "SELECT id,workspace_id,email,role,expires_at,created_at FROM invitations WHERE id=?",
                    (cursor.lastrowid,),
                ).fetchone()
            )
            return invite, token

    def accept_invitation(self, token: str, user_id: int) -> Optional[int]:
        now = to_iso(utc_now())
        with connection(self.database_path) as conn:
            invite = conn.execute(
                "SELECT i.*,u.email user_email FROM invitations i JOIN users u ON u.id=? WHERE i.token_hash=? AND i.accepted_at IS NULL AND i.revoked_at IS NULL AND i.expires_at>?",
                (user_id, hash_token(token), now),
            ).fetchone()
            if not invite or invite["email"].lower() != invite["user_email"].lower():
                return None
            conn.execute(
                "INSERT OR IGNORE INTO workspace_members (workspace_id,user_id,role,joined_at) VALUES (?,?,?,?)",
                (invite["workspace_id"], user_id, invite["role"], now),
            )
            conn.execute(
                "UPDATE invitations SET accepted_at=? WHERE id=?", (now, invite["id"])
            )
            return int(invite["workspace_id"])

    def update_member_role(self, workspace_id: int, user_id: int, role: str) -> bool:
        with connection(self.database_path) as conn:
            current = conn.execute(
                "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
                (workspace_id, user_id),
            ).fetchone()
            if not current or current["role"] == "OWNER":
                return False
            return (
                conn.execute(
                    "UPDATE workspace_members SET role=? WHERE workspace_id=? AND user_id=?",
                    (role, workspace_id, user_id),
                ).rowcount
                > 0
            )

    def update_user_profile(
        self, user_id: int, full_name: str, job_title: str, email: str, phone: str
    ) -> Optional[dict]:
        now = to_iso(utc_now())
        with connection(self.database_path) as conn:
            conn.execute(
                "UPDATE users SET full_name=?,job_title=?,email=?,phone=?,updated_at=? WHERE id=?",
                (full_name, job_title, email.lower(), phone, now, user_id),
            )
            row = conn.execute(
                "SELECT id,email,full_name,job_title,phone FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None
