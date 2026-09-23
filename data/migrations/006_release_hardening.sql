CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0,1)),
    delivery_status TEXT NOT NULL DEFAULT 'CREATED' CHECK (delivery_status IN ('CREATED','DELIVERED','FAILED')),
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    UNIQUE(workspace_id,idempotency_key)
);

CREATE TABLE IF NOT EXISTS export_jobs (
    id TEXT PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    created_by INTEGER NOT NULL REFERENCES users(id),
    format TEXT NOT NULL CHECK (format IN ('CSV','XLSX','PDF')),
    export_type TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK (status IN ('PENDING','PROCESSING','COMPLETED','FAILED')),
    stored_filename TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    request_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notifications_workspace_user ON notifications(workspace_id,user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_export_jobs_workspace_created ON export_jobs(workspace_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_workspace_created ON audit_logs(workspace_id,created_at DESC);
