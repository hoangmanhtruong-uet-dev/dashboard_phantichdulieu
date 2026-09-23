CREATE TABLE IF NOT EXISTS background_jobs (
    id TEXT PRIMARY KEY,
    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL CHECK (job_type IN ('IMPORT','EXPORT','NOTIFICATION')),
    resource_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')),
    correlation_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    error_summary TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id,job_type,idempotency_key)
);

ALTER TABLE import_jobs ADD COLUMN object_key TEXT;
ALTER TABLE import_jobs ADD COLUMN queue_job_id TEXT;
ALTER TABLE import_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE import_jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3;

ALTER TABLE export_jobs ADD COLUMN object_key TEXT;
ALTER TABLE export_jobs ADD COLUMN queue_job_id TEXT;
ALTER TABLE export_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE export_jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3;
ALTER TABLE export_jobs ADD COLUMN started_at TEXT;

ALTER TABLE notifications ADD COLUMN queue_job_id TEXT;
ALTER TABLE notifications ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE notifications ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3;
ALTER TABLE notifications ADD COLUMN failure_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_background_jobs_workspace_status ON background_jobs(workspace_id,status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_background_jobs_resource ON background_jobs(job_type,resource_id);
