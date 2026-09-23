from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from data.database import DatabaseTarget, connection, is_postgres, table_exists


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

ALTER_ADD_COLUMN = re.compile(
    r"^ALTER\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s+ADD\s+COLUMN\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def postgres_sql(sql: str) -> str:
    """Translate the deliberately conservative SQLite migration subset to Postgres."""
    translated = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "BIGSERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r"TEXT(\s+NOT\s+NULL)?\s+COLLATE\s+NOCASE",
        lambda match: "CITEXT" + (match.group(1) or ""),
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(r"\bDATETIME\b", "TEXT", translated, flags=re.IGNORECASE)
    translated = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO\s+(.+?)(?=\nSELECT)",
        r"INSERT INTO \1",
        translated,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Only migration 005 uses INSERT OR IGNORE and its natural conflict target is
    # the declared (workspace_id,event_id) uniqueness constraint.
    if "INSERT OR IGNORE" in sql.upper():
        translated = translated.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING;"
    return translated


def _column_exists(
    conn: Any, table_name: str, column_name: str, postgres: bool
) -> bool:
    if postgres:
        return (
            conn.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=? AND column_name=?",
                (table_name, column_name),
            ).fetchone()
            is not None
        )
    return column_name.lower() in {
        row["name"].lower() for row in conn.execute(f"PRAGMA table_info({table_name})")
    }


def _execute_migration(conn: Any, sql: str, *, postgres: bool) -> None:
    """Execute DDL transactionally and make additive columns restart-safe."""
    if postgres:
        sql = postgres_sql(sql)
    for fragment in sql.split(";"):
        statement = fragment.strip()
        if not statement:
            continue
        match = ALTER_ADD_COLUMN.match(statement)
        if match:
            table_name, column_name = match.groups()
            if _column_exists(conn, table_name, column_name, postgres):
                continue
        conn.execute(statement)


def run_migrations(
    target: DatabaseTarget, through_version: str | None = None
) -> list[str]:
    applied_now: list[str] = []
    postgres = is_postgres(target)
    with connection(target) as conn:
        if postgres:
            conn.execute("CREATE EXTENSION IF NOT EXISTS citext")
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
            if through_version is not None and version > through_version:
                continue
            sql = migration_path.read_text(encoding="utf-8")
            checksum = sha256(sql.encode("utf-8")).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(f"Migration {version} checksum mismatch")
                continue
            _execute_migration(conn, sql, postgres=postgres)
            conn.execute(
                "INSERT INTO schema_migrations (version,checksum) VALUES (?,?)",
                (version, checksum),
            )
            applied_now.append(migration_path.name)
    return applied_now


def migration_status(target: DatabaseTarget) -> dict[str, Any]:
    files = sorted(path.name for path in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    postgres = is_postgres(target)
    with connection(target) as conn:
        exists = table_exists(conn, "schema_migrations", postgres=postgres)
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
    expected = [name.split("_", 1)[0] for name in files]
    return {"files": files, "applied": applied, "current": expected == applied}


if __name__ == "__main__":
    from backend.config import settings

    applied = run_migrations(settings.database_path)
    status = migration_status(settings.database_path)
    print({"applied_now": applied, **status})
