"""Create an online-consistent SQLite backup without stopping the API."""

import argparse
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def create_backup(source: Path, destination_dir: Path) -> Path:
    source = source.resolve()
    destination_dir = destination_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = destination_dir / f"nexus-{stamp}.sqlite3"
    with (
        closing(sqlite3.connect(source)) as source_db,
        closing(sqlite3.connect(destination)) as backup_db,
    ):
        source_db.backup(backup_db)
        result = backup_db.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"Backup integrity check failed: {result}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(create_backup(args.database, args.destination))
