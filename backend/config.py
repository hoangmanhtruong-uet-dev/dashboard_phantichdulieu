from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALID_ENVIRONMENTS = {"development", "staging", "production", "test"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_path: Path | str
    database_url: str
    cors_origins: tuple[str, ...]
    seed_demo_data: bool
    port: int
    jwt_secret: str
    access_token_minutes: int
    refresh_token_days: int
    session_days: int
    cookie_secure: bool
    upload_dir: Path
    export_dir: Path
    max_upload_bytes: int
    max_import_rows: int
    max_import_columns: int
    preview_rows: int
    max_cell_chars: int
    max_workbook_uncompressed_bytes: int
    redis_url: str
    storage_backend: str
    s3_bucket: str
    s3_region: str
    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: str
    sentry_dsn: str
    queue_name: str
    retention_days: int

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @classmethod
    def from_environment(cls) -> "Settings":
        app_env = os.getenv("APP_ENV", "development").strip().lower()
        if app_env not in VALID_ENVIRONMENTS:
            raise RuntimeError(
                f"APP_ENV must be one of: {', '.join(sorted(VALID_ENVIRONMENTS))}"
            )

        database_url = os.getenv("DATABASE_URL", "").strip()
        database_value = os.getenv("DATABASE_PATH", "").strip()
        cors_value = os.getenv("CORS_ORIGINS", "").strip()
        if app_env in {"staging", "production"} and not database_url:
            raise RuntimeError(
                "DATABASE_URL (PostgreSQL) is required in staging and production"
            )
        if database_url and not database_url.startswith(
            ("postgresql://", "postgres://")
        ):
            raise RuntimeError("DATABASE_URL must use PostgreSQL")
        if app_env in {"staging", "production"} and not cors_value:
            raise RuntimeError("CORS_ORIGINS is required in staging and production")

        jwt_secret = os.getenv("JWT_SECRET", "").strip()
        if app_env in {"staging", "production"} and len(jwt_secret) < 32:
            raise RuntimeError(
                "JWT_SECRET must contain at least 32 characters in staging and production"
            )
        if not jwt_secret:
            jwt_secret = "development-only-nexus-secret-change-me"

        if database_url:
            database_path: Path | str = database_url
        else:
            database_path = (
                Path(database_value) if database_value else PROJECT_ROOT / "sales.db"
            )
            if not database_path.is_absolute():
                database_path = (PROJECT_ROOT / database_path).resolve()

        if cors_value:
            cors_origins = tuple(
                origin.strip() for origin in cors_value.split(",") if origin.strip()
            )
        elif app_env in {"development", "test"}:
            cors_origins = ("*",)
        else:
            cors_origins = ()

        seed_default = app_env in {"development", "test"}
        seed_demo_data = os.getenv(
            "SEED_DEMO_DATA", str(seed_default)
        ).strip().lower() in {"1", "true", "yes", "on"}
        port_text = os.getenv("PORT", "8000")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise RuntimeError("PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise RuntimeError("PORT must be between 1 and 65535")

        access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
        refresh_token_days = int(os.getenv("REFRESH_TOKEN_DAYS", "30"))
        session_days = int(os.getenv("SESSION_DAYS", "30"))
        if access_token_minutes < 1 or refresh_token_days < 1 or session_days < 1:
            raise RuntimeError("Token and session lifetimes must be positive")

        upload_value = os.getenv("UPLOAD_DIR", "").strip()
        local_data_root = (
            database_path.parent
            if isinstance(database_path, Path)
            else PROJECT_ROOT / ".data"
        )
        upload_dir = Path(upload_value) if upload_value else local_data_root / "uploads"
        if not upload_dir.is_absolute():
            upload_dir = (PROJECT_ROOT / upload_dir).resolve()
        export_value = os.getenv("EXPORT_DIR", "").strip()
        export_dir = Path(export_value) if export_value else local_data_root / "exports"
        if not export_dir.is_absolute():
            export_dir = (PROJECT_ROOT / export_dir).resolve()
        max_upload_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
        max_import_rows = int(os.getenv("MAX_IMPORT_ROWS", "100000"))
        max_import_columns = int(os.getenv("MAX_IMPORT_COLUMNS", "100"))
        preview_rows = int(os.getenv("PREVIEW_ROWS", "20"))
        max_cell_chars = int(os.getenv("MAX_CELL_CHARS", "10000"))
        max_workbook_uncompressed_bytes = int(
            os.getenv("MAX_WORKBOOK_UNCOMPRESSED_BYTES", str(100 * 1024 * 1024))
        )
        if (
            min(
                max_upload_bytes,
                max_import_rows,
                max_import_columns,
                preview_rows,
                max_cell_chars,
            )
            < 1
        ):
            raise RuntimeError("Upload and ingestion limits must be positive")
        if max_workbook_uncompressed_bytes < max_upload_bytes:
            raise RuntimeError(
                "MAX_WORKBOOK_UNCOMPRESSED_BYTES must be at least MAX_UPLOAD_BYTES"
            )

        redis_url = os.getenv("REDIS_URL", "").strip()
        storage_backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
        if storage_backend not in {"local", "s3"}:
            raise RuntimeError("STORAGE_BACKEND must be local or s3")
        s3_bucket = os.getenv("S3_BUCKET", "").strip()
        s3_region = os.getenv("S3_REGION", "us-east-1").strip()
        s3_endpoint_url = os.getenv("S3_ENDPOINT_URL", "").strip()
        s3_access_key_id = os.getenv("S3_ACCESS_KEY_ID", "").strip()
        s3_secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
        sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
        if app_env in {"staging", "production"}:
            if not redis_url:
                raise RuntimeError("REDIS_URL is required in staging and production")
            if storage_backend != "s3" or not s3_bucket:
                raise RuntimeError(
                    "Private S3 storage and S3_BUCKET are required in staging and production"
                )
            if not sentry_dsn:
                raise RuntimeError("SENTRY_DSN is required in staging and production")

        retention_days = int(os.getenv("OBJECT_RETENTION_DAYS", "30"))
        if retention_days < 1:
            raise RuntimeError("OBJECT_RETENTION_DAYS must be positive")

        return cls(
            app_env=app_env,
            database_path=database_path,
            database_url=database_url,
            cors_origins=cors_origins,
            seed_demo_data=seed_demo_data,
            port=port,
            jwt_secret=jwt_secret,
            access_token_minutes=access_token_minutes,
            refresh_token_days=refresh_token_days,
            session_days=session_days,
            cookie_secure=app_env in {"staging", "production"},
            upload_dir=upload_dir,
            export_dir=export_dir,
            max_upload_bytes=max_upload_bytes,
            max_import_rows=max_import_rows,
            max_import_columns=max_import_columns,
            preview_rows=preview_rows,
            max_cell_chars=max_cell_chars,
            max_workbook_uncompressed_bytes=max_workbook_uncompressed_bytes,
            redis_url=redis_url,
            storage_backend=storage_backend,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            s3_endpoint_url=s3_endpoint_url,
            s3_access_key_id=s3_access_key_id,
            s3_secret_access_key=s3_secret_access_key,
            sentry_dsn=sentry_dsn,
            queue_name=os.getenv("QUEUE_NAME", "nexus-jobs").strip() or "nexus-jobs",
            retention_days=retention_days,
        )


settings = Settings.from_environment()
