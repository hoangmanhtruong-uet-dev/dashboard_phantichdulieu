"""Restore a private S3 backup into a dedicated non-production drill database."""

import os
from pathlib import Path
import subprocess
import tempfile


def main() -> None:
    source_url = os.environ.get("DATABASE_URL", "").strip()
    restore_url = os.environ.get("RESTORE_DATABASE_URL", "").strip()
    bucket = os.environ.get("BACKUP_S3_BUCKET", "").strip()
    key = os.environ.get("BACKUP_OBJECT_KEY", "").strip()
    if not restore_url or restore_url == source_url:
        raise RuntimeError("RESTORE_DATABASE_URL must be a separate drill database")
    if not bucket or not key:
        raise RuntimeError("BACKUP_S3_BUCKET and BACKUP_OBJECT_KEY are required")
    with tempfile.TemporaryDirectory(prefix="nexus-restore-") as directory:
        dump = Path(directory) / "nexus.dump"
        import boto3

        client = boto3.client(
            "s3",
            region_name=os.environ.get("S3_REGION") or "us-east-1",
            endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY") or None,
        )
        client.download_file(bucket, key, str(dump))
        subprocess.run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                "--dbname",
                restore_url,
                str(dump),
            ],
            check=True,
            timeout=1800,
        )
        subprocess.run(
            [
                "psql",
                restore_url,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "SELECT COUNT(*) FROM schema_migrations;",
            ],
            check=True,
            timeout=60,
        )
        print({"status": "restore_verified", "object_key": key})


if __name__ == "__main__":
    main()
