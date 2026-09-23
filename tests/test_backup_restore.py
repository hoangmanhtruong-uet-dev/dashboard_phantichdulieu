import tempfile
import unittest
from pathlib import Path

from data.migrate import run_migrations
from data.database import connection
from scripts.backup_database import create_backup
from scripts.verify_backup import verify_backup


class BackupRestoreTests(unittest.TestCase):
    def test_online_backup_can_be_restored_and_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "live.sqlite3"
            run_migrations(database)
            with connection(database) as conn:
                conn.execute(
                    "INSERT INTO users (email,password_hash,full_name,created_at,updated_at) VALUES ('backup@example.com','hash','Backup User','2026-01-01','2026-01-01')"
                )
                user_id = conn.execute(
                    "SELECT id FROM users WHERE email='backup@example.com'"
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO workspaces (name,slug,created_by,created_at) VALUES ('Backup','backup',?,'2026-01-01')",
                    (user_id,),
                )
            backup = create_backup(database, root / "backups")
            result = verify_backup(backup)
            self.assertEqual("ok", result["integrity"])
            self.assertEqual(7, result["migrations"])
            self.assertEqual(1, result["workspaces"])


if __name__ == "__main__":
    unittest.main()
