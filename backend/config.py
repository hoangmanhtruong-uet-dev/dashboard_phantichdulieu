from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALID_ENVIRONMENTS = {"development", "staging", "production", "test"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_path: Path
    cors_origins: tuple[str, ...]
    seed_demo_data: bool
    port: int
    jwt_secret: str
    access_token_minutes: int
    refresh_token_days: int
    session_days: int
    cookie_secure: bool
    upload_dir: Path
    max_upload_bytes: int
    max_import_rows: int
    max_import_columns: int
    preview_rows: int
    max_cell_chars: int
    max_workbook_uncompressed_bytes: int

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

        database_value = os.getenv("DATABASE_PATH", "").strip()
        cors_value = os.getenv("CORS_ORIGINS", "").strip()
        if app_env == "production" and not database_value:
            raise RuntimeError("DATABASE_PATH is required when APP_ENV=production")
        if app_env == "production" and not cors_value:
            raise RuntimeError("CORS_ORIGINS is required when APP_ENV=production")

        jwt_secret = os.getenv("JWT_SECRET", "").strip()
        if app_env == "production" and len(jwt_secret) < 32:
            raise RuntimeError(
                "JWT_SECRET must contain at least 32 characters when APP_ENV=production"
            )
        if not jwt_secret:
            jwt_secret = "development-only-nexus-secret-change-me"

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
        upload_dir = (
            Path(upload_value) if upload_value else database_path.parent / "uploads"
        )
        if not upload_dir.is_absolute():
            upload_dir = (PROJECT_ROOT / upload_dir).resolve()
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

        return cls(
            app_env=app_env,
            database_path=database_path,
            cors_origins=cors_origins,
            seed_demo_data=seed_demo_data,
            port=port,
            jwt_secret=jwt_secret,
            access_token_minutes=access_token_minutes,
            refresh_token_days=refresh_token_days,
            session_days=session_days,
            cookie_secure=app_env == "production",
            upload_dir=upload_dir,
            max_upload_bytes=max_upload_bytes,
            max_import_rows=max_import_rows,
            max_import_columns=max_import_columns,
            preview_rows=preview_rows,
            max_cell_chars=max_cell_chars,
            max_workbook_uncompressed_bytes=max_workbook_uncompressed_bytes,
        )


settings = Settings.from_environment()
