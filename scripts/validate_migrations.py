import tempfile
from pathlib import Path

from data.database import connection
from data.migrate import migration_status, run_migrations


with tempfile.TemporaryDirectory(prefix="nexus-migrations-") as temp:
    database = Path(temp) / "validation.sqlite3"
    first = run_migrations(database)
    second = run_migrations(database)
    status = migration_status(database)
    with connection(database) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if not first or second or not status["current"] or integrity != "ok":
        raise SystemExit(
            {"first": first, "second": second, "status": status, "integrity": integrity}
        )
    print({"migrations": first, "restart_safe": True, "integrity": integrity})
