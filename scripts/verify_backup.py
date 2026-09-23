"""Restore a backup into an isolated temporary database and validate it."""

import argparse
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


def verify_backup(backup: Path) -> dict:
    backup = backup.resolve()
    if not backup.is_file():
        raise FileNotFoundError(backup)
    with tempfile.TemporaryDirectory(prefix="nexus-restore-test-") as temp:
        restored = Path(temp) / "restored.sqlite3"
        shutil.copy2(backup, restored)
        with closing(sqlite3.connect(restored)) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            migrations = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations"
            ).fetchone()[0]
            workspaces = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Restore validation failed: {integrity}")
        return {
            "integrity": integrity,
            "migrations": migrations,
            "workspaces": workspaces,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    print(verify_backup(parser.parse_args().backup))
