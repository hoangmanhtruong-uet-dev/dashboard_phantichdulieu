"""Create a PostgreSQL custom-format backup and store it in private S3."""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import tempfile


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    bucket = os.environ.get("BACKUP_S3_BUCKET", "").strip()
    backup_prefix = os.environ.get("BACKUP_PREFIX", "").strip().strip("/")
    if not database_url.startswith(("postgresql://", "postgres://")) or not bucket:
        raise RuntimeError("DATABASE_URL and BACKUP_S3_BUCKET are required")
    if not backup_prefix:
        raise RuntimeError("BACKUP_PREFIX is required")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{backup_prefix}/{stamp}/nexus.dump"
    with tempfile.TemporaryDirectory(prefix="nexus-backup-") as directory:
        destination = Path(directory) / "nexus.dump"
        subprocess.run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(destination),
                database_url,
            ],
            check=True,
            timeout=1800,
        )
        import boto3

        client = boto3.client(
            "s3",
            region_name=os.environ.get("S3_REGION") or "us-east-1",
            endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY") or None,
        )
        client.upload_file(
            str(destination),
            bucket,
            key,
            ExtraArgs={"ContentType": "application/octet-stream"},
        )
        print({"status": "completed", "object_key": key})


if __name__ == "__main__":
    main()
