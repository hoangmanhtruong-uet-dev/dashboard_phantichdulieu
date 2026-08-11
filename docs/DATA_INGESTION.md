# Phase 3 data ingestion

## Supported flow

`Upload -> Parse -> Preview -> Column Mapping -> Validation -> Import -> Completed / Failed`

CSV and XLSX are the only supported formats. External analytics providers, OAuth
and AI are deliberately outside this phase.

## Limits and trust boundary

Defaults are 10 MB per upload, 100,000 data rows, 100 columns, 10,000 characters
per cell and 100 MB total uncompressed XLSX content. The server generates the job
ID and stored filename, strips client paths from display names, and validates the
resolved storage location.

Extension, allowed MIME type, signature where available, empty content, workbook
archive safety, sheets, columns, row counts and malformed input are validated.
XLSX macros are refused and formulas are never evaluated. Errors expose source
row, canonical field and stable code, never an internal stack trace.

## Model boundary

- `import_jobs`: durable workflow and history.
- `import_errors`: user-facing row failures.
- `raw_import_records`: untrusted source values.
- `data_sources`: resulting `FILE_UPLOAD` source and health.
- `orders`: normalized analytics values used by existing metrics.

Idempotency uses active workspace plus SHA-256 content hash, not filename. A
partial unique database index is the final concurrency guard for completed jobs.

There was no existing queue. Processing is synchronous with durable transitions
through `UPLOADED`, `PREVIEWED`, `VALIDATING`, `PROCESSING`, `COMPLETED`, `FAILED`
or `CANCELLED`; no fake percentage is returned.

## UI to API to database mapping

| UI screen/action | API endpoint | Database entity | Status |
|---|---|---|---|
| Mobile 20 / Desktop Data: choose file | `POST /api/ingestion/uploads` | `import_jobs` + server file | `UPLOADED` |
| Automatic preview | `POST /api/ingestion/jobs/{id}/preview` | `import_jobs.preview_json` | `PREVIEWED` or `FAILED` |
| Column mapping form | `GET /api/ingestion/schema` and preview response | `import_jobs.mapping_json` on import | `PREVIEWED` |
| Check and import | `POST /api/ingestion/jobs/{id}/import` | `raw_import_records`, `import_errors`, `orders`, `data_sources` | `VALIDATING` -> `PROCESSING` -> `COMPLETED`, or `FAILED` |
| Import history | `GET /api/ingestion/jobs` | `import_jobs`, `users`, `data_sources` | exact durable status |
| Failure detail | `GET /api/ingestion/jobs/{id}/errors` | `import_errors` | exact row errors |
| Source history | `GET /api/ingestion/sources/{id}/history` | `data_sources`, `import_jobs` | exact durable status |
| Cancel before processing | `POST /api/ingestion/jobs/{id}/cancel` | `import_jobs` | `CANCELLED` |

All repository access derives `workspace_id` from the authenticated session.
Changing an ID cannot cross the workspace boundary. Upload/import requires
`ADMIN` or `OWNER`; server authorization remains authoritative.
