from hashlib import sha256
from pathlib import Path
import re

from data.database import connection


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


ALTER_ADD_COLUMN = re.compile(
    r"^ALTER\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s+ADD\s+COLUMN\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def _execute_migration(conn, sql: str) -> None:
    """Execute DDL transactionally and make additive columns restart-safe."""
    for fragment in sql.split(";"):
        statement = fragment.strip()
        if not statement:
            continue
        match = ALTER_ADD_COLUMN.match(statement)
        if match:
            table_name, column_name = match.groups()
            existing = {
                row["name"].lower()
                for row in conn.execute(f"PRAGMA table_info({table_name})")
            }
            if column_name.lower() in existing:
                continue
        conn.execute(statement)


def run_migrations(database_path: Path) -> list[str]:
    applied_now = []
    with connection(database_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version TEXT PRIMARY KEY,
                   checksum TEXT NOT NULL,
                   applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        applied = {
            row["version"]: row["checksum"]
            for row in conn.execute("SELECT version,checksum FROM schema_migrations")
        }
        for migration_path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")):
            version = migration_path.name.split("_", 1)[0]
            sql = migration_path.read_text(encoding="utf-8")
            checksum = sha256(sql.encode("utf-8")).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(f"Migration {version} checksum mismatch")
                continue
            _execute_migration(conn, sql)
            conn.execute(
                "INSERT INTO schema_migrations (version,checksum) VALUES (?,?)",
                (version, checksum),
            )
            applied_now.append(migration_path.name)
    return applied_now


def migration_status(database_path: Path) -> dict:
    files = sorted(path.name for path in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    with connection(database_path) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        applied = (
            []
            if not exists
            else [
                row["version"]
                for row in conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ]
        )
    return {"files": files, "applied": applied, "current": len(files) == len(applied)}


if __name__ == "__main__":
    from backend.config import settings

    applied = run_migrations(settings.database_path)
    status = migration_status(settings.database_path)
    print({"applied_now": applied, **status})
