from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from typing import BinaryIO, Iterator

from backend.config import Settings


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("Unsafe object key")
        return candidate

    def put_file(self, source: Path, key: str, content_type: str) -> None:
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    def put_stream(self, stream: BinaryIO, key: str, content_type: str) -> None:
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            shutil.copyfileobj(stream, handle)

    @contextmanager
    def materialize(self, key: str) -> Iterator[Path]:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        yield path

    def download_url(self, key: str, expires: int = 300) -> str | None:
        return None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def health(self) -> bool:
        probe = self.root / ".health"
        try:
            probe.touch(exist_ok=True)
            return probe.is_file()
        except OSError:
            return False


class S3Storage:
    def __init__(self, settings: Settings):
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("S3 support requires boto3") from exc
        kwargs = {
            "region_name": settings.s3_region,
            "endpoint_url": settings.s3_endpoint_url or None,
        }
        if settings.s3_access_key_id:
            kwargs["aws_access_key_id"] = settings.s3_access_key_id
        if settings.s3_secret_access_key:
            kwargs["aws_secret_access_key"] = settings.s3_secret_access_key
        self.client = boto3.client("s3", **kwargs)
        self.bucket = settings.s3_bucket

    def put_file(self, source: Path, key: str, content_type: str) -> None:
        self.client.upload_file(
            str(source), self.bucket, key, ExtraArgs={"ContentType": content_type}
        )

    def put_stream(self, stream: BinaryIO, key: str, content_type: str) -> None:
        self.client.upload_fileobj(
            stream, self.bucket, key, ExtraArgs={"ContentType": content_type}
        )

    @contextmanager
    def materialize(self, key: str) -> Iterator[Path]:
        suffix = Path(key).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            path = Path(handle.name)
        try:
            self.client.download_file(self.bucket, key, str(path))
            yield path
        finally:
            path.unlink(missing_ok=True)

    def download_url(self, key: str, expires: int = 300) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def health(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False


def create_storage(settings: Settings, local_root: Path | None = None):
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return LocalStorage(local_root or settings.upload_dir.parent / "objects")
