# Nexus Analytics architecture

## Runtime

The deployed product remains a single FastAPI service so the existing Render entrypoint and same-origin frontend URLs remain compatible.

- `index.html`, `style.css`, `app.js`: approved UI and screen composition.
- `frontend/`: frontend infrastructure such as the centralized API client.
- `ai_service.py`: compatibility entrypoint and current HTTP route composition.
- `backend/`: server configuration, authentication/RBAC, input schemas, response helpers and centralized errors.
- `data/`: SQLite connection policy, deterministic migrations and explicit development seeds.
- `docs/`: architecture, API contract and mock-data migration inventory.
- `tests/`: API and migration regression tests.

## Dependency direction

`frontend -> HTTP API`

`ai_service -> backend + data`

`backend/auth -> data/auth_repository`

`backend/ingestion -> data/ingestion_repository`

`data -> no backend or frontend dependency`

The project keeps `ai_service:app` as the public entrypoint. Phase 2 authentication and workspace routes are isolated in FastAPI routers while legacy analytics routes stay compatible.

## Configuration

Server configuration is loaded once by `backend.config.Settings`. Production fails during import when mandatory `DATABASE_PATH` or `CORS_ORIGINS` configuration is missing. Development defaults are never selected when `APP_ENV=production`.

Client code uses same-origin requests by default. A future split deployment may set `window.NEXUS_CONFIG.apiBaseUrl`; it must never contain secrets.

Authentication uses short-lived signed access JWTs and opaque rotating refresh tokens in HttpOnly cookies. Only refresh-token hashes are stored. The readable CSRF cookie is not an authentication secret and must match the request header on unsafe operations.

## Database

SQLite connections are short-lived and managed by `data.database.connection`. Schema changes are ordered SQL files under `data/migrations/`, recorded in `schema_migrations`, and protected by checksums. Demo records are not migrations and only run when `SEED_DEMO_DATA=true`.

Workspace-owned tables include `workspace_id`, and all repository reads/mutations require it. Identity, membership, invitation, session, refresh and reset-token records are normalized in migration `003_auth_workspaces.sql`.

Migration `004_file_ingestion.sql` adds durable import jobs, row-level errors,
raw records, FILE_UPLOAD source metadata, and links normalized records to the
existing `orders` analytics model. Raw uploaded values stay in
`raw_import_records`; validated canonical values enter `orders`. This avoids a
premature general-purpose BI warehouse.

## Ingestion runtime

Uploads stream in fixed-size chunks to server-generated filenames. CSV is read
row-by-row and XLSX uses read-only worksheets. Validation and normalized inserts
use bounded batches. There is no existing queue, so imports run synchronously and
persist only real states instead of simulated progress.

Formula cells are untrusted and rejected when mapped. Macro-enabled archives,
unsafe archive members and oversized expanded workbooks are rejected. No external
analytics provider is connected.

## Legacy files

- `SalesController.java` is an unbuilt historical Spring prototype and is not part of runtime.
- `db_simulator.py` is an opt-in local data generator and is not started by the application.
- `models.txt` is a historical provider-model inventory and is not loaded by runtime.

These files are retained in Phase 1 to avoid destructive cleanup without a separate approval.
