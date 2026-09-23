from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
from threading import Lock
from typing import Any, Iterator


DatabaseTarget = Path | str
_pools: dict[str, Any] = {}
_pool_lock = Lock()


def is_postgres(target: DatabaseTarget) -> bool:
    return isinstance(target, str) and target.startswith(
        ("postgresql://", "postgres://")
    )


def _postgres_pool(url: str):
    try:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError as exc:  # pragma: no cover - dependency failure is explicit
        raise RuntimeError(
            "PostgreSQL support requires psycopg and psycopg-pool"
        ) from exc
    with _pool_lock:
        pool = _pools.get(url)
        if pool is None:
            pool = ConnectionPool(
                conninfo=url,
                min_size=1,
                max_size=10,
                timeout=5,
                kwargs={"row_factory": dict_row, "connect_timeout": 5},
                open=True,
            )
            _pools[url] = pool
        return pool


def _translate_parameters(sql: str) -> str:
    """Translate the repository's DB-API qmark placeholders for psycopg."""
    translated = sql.replace("?", "%s")
    translated = re.sub(r"\s+COLLATE\s+NOCASE", "", translated, flags=re.IGNORECASE)
    translated = re.sub(r"datetime\(([^()]+)\)", r"\1", translated, flags=re.IGNORECASE)
    translated = re.sub(
        r"date\(([^()]+)\)", r"substr(\1,1,10)", translated, flags=re.IGNORECASE
    )
    translated = re.sub(
        r"ROUND\(SUM\(([^)]+)\),\s*2\)",
        r"ROUND(CAST(SUM(\1) AS numeric),2)",
        translated,
        flags=re.IGNORECASE,
    )
    if re.match(r"^\s*INSERT\s+OR\s+IGNORE", translated, re.IGNORECASE):
        translated = re.sub(
            r"INSERT\s+OR\s+IGNORE", "INSERT", translated, flags=re.IGNORECASE
        )
        translated = translated.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return translated


_INSERT_ID = re.compile(
    r"^\s*INSERT\s+INTO\s+(users|workspaces|workspace_members|invitations|sessions|password_reset_tokens|data_sources|import_jobs|import_errors|raw_import_records|normalized_analytics_records|reports|alerts|saved_views|notifications|audit_logs|export_jobs|background_jobs|analytics_events|analytics_segments)\b",
    re.IGNORECASE,
)


class PostgresCursor:
    def __init__(self, cursor: Any, lastrowid: int | None = None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def __iter__(self):
        return iter(self._cursor)


class PostgresConnection:
    def __init__(self, raw: Any):
        self.raw = raw

    def execute(self, sql: str, params: Any = None) -> PostgresCursor:
        translated = _translate_parameters(sql)
        lower_sql = translated.lower()
        wants_id = (
            bool(_INSERT_ID.match(translated))
            and " returning " not in lower_sql
            and "\nselect " not in lower_sql
        )
        if wants_id:
            translated = translated.rstrip().rstrip(";") + " RETURNING id"
        cursor = self.raw.execute(translated, params or ())
        lastrowid = None
        if wants_id:
            row = cursor.fetchone()
            lastrowid = int(row["id"])
        return PostgresCursor(cursor, lastrowid)

    def executemany(self, sql: str, params: Any) -> PostgresCursor:
        return PostgresCursor(self.raw.executemany(_translate_parameters(sql), params))

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()


@contextmanager
def connection(target: DatabaseTarget) -> Iterator[Any]:
    if is_postgres(target):
        pool = _postgres_pool(str(target))
        with pool.connection() as raw:
            conn = PostgresConnection(raw)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return

    database_path = Path(target)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_conn = sqlite3.connect(database_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_conn.execute("PRAGMA foreign_keys=ON")
    sqlite_conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield sqlite_conn
        sqlite_conn.commit()
    except Exception:
        sqlite_conn.rollback()
        raise
    finally:
        sqlite_conn.close()


def close_pools() -> None:
    with _pool_lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()


def is_integrity_error(error: BaseException) -> bool:
    if isinstance(error, sqlite3.IntegrityError):
        return True
    try:
        from psycopg import IntegrityError

        return isinstance(error, IntegrityError)
    except ImportError:
        return False


def table_exists(conn: Any, table_name: str, *, postgres: bool) -> bool:
    if postgres:
        return (
            conn.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=?",
                (table_name,),
            ).fetchone()
            is not None
        )
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        is not None
    )
