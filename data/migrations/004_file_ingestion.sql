CREATE TABLE IF NOT EXISTS import_jobs (
    id TEXT PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    data_source_id INTEGER REFERENCES data_sources(id) ON DELETE SET NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size > 0),
    mime_type TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('CSV','XLSX')),
    sheet_name TEXT,
    status TEXT NOT NULL CHECK (status IN ('UPLOADED','PREVIEWED','VALIDATING','PROCESSING','COMPLETED','FAILED','CANCELLED')),
    row_count INTEGER,
    valid_rows INTEGER NOT NULL DEFAULT 0,
    invalid_rows INTEGER NOT NULL DEFAULT 0,
    column_count INTEGER,
    mapping_json TEXT,
    preview_json TEXT,
    error_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS import_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    error_code TEXT NOT NULL,
    message TEXT NOT NULL,
    raw_value TEXT
);

CREATE TABLE IF NOT EXISTS raw_import_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    row_hash TEXT NOT NULL,
    UNIQUE(job_id,row_number)
);

ALTER TABLE data_sources ADD COLUMN created_by INTEGER REFERENCES users(id);
ALTER TABLE data_sources ADD COLUMN created_at TEXT;
ALTER TABLE data_sources ADD COLUMN last_import_at TEXT;
ALTER TABLE data_sources ADD COLUMN event_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE data_sources ADD COLUMN health_status TEXT NOT NULL DEFAULT 'UNKNOWN';

ALTER TABLE orders ADD COLUMN import_job_id TEXT REFERENCES import_jobs(id) ON DELETE SET NULL;
ALTER TABLE orders ADD COLUMN data_source_id INTEGER REFERENCES data_sources(id) ON DELETE SET NULL;
ALTER TABLE orders ADD COLUMN source TEXT;
ALTER TABLE orders ADD COLUMN product TEXT;
ALTER TABLE orders ADD COLUMN currency TEXT;
ALTER TABLE orders ADD COLUMN is_conversion INTEGER NOT NULL DEFAULT 1 CHECK (is_conversion IN (0,1));
ALTER TABLE orders ADD COLUMN raw_record_id INTEGER REFERENCES raw_import_records(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_import_jobs_workspace_created ON import_jobs(workspace_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_jobs_source ON import_jobs(data_source_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_import_completed_hash ON import_jobs(workspace_id,file_hash) WHERE status='COMPLETED';
CREATE INDEX IF NOT EXISTS idx_import_errors_job_row ON import_errors(job_id,row_number);
CREATE INDEX IF NOT EXISTS idx_raw_records_job_row ON raw_import_records(job_id,row_number);
CREATE INDEX IF NOT EXISTS idx_orders_import_job ON orders(import_job_id);
CREATE INDEX IF NOT EXISTS idx_sources_workspace_type ON data_sources(workspace_id,source_type);
