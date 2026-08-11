CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    job_title TEXT NOT NULL DEFAULT 'Member',
    phone TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('OWNER','ADMIN','ANALYST','VIEWER')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id,user_id)
);

CREATE TABLE IF NOT EXISTS invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email TEXT NOT NULL COLLATE NOCASE,
    role TEXT NOT NULL CHECK (role IN ('ADMIN','ANALYST','VIEWER')),
    token_hash TEXT NOT NULL UNIQUE,
    invited_by INTEGER NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL,
    accepted_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    active_workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    ip_address TEXT,
    user_agent TEXT
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES auth_sessions(id) ON DELETE CASCADE,
    family_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    rotated_from TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT
);

ALTER TABLE orders ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
ALTER TABLE insights ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
ALTER TABLE alerts ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
ALTER TABLE reports ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
ALTER TABLE data_sources ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
ALTER TABLE saved_views ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);

CREATE INDEX IF NOT EXISTS idx_members_user ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS idx_invitations_workspace_email ON invitations(workspace_id,email);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON auth_sessions(user_id,revoked_at);
CREATE INDEX IF NOT EXISTS idx_refresh_session ON refresh_tokens(session_id,revoked_at);
CREATE INDEX IF NOT EXISTS idx_refresh_family ON refresh_tokens(family_id);
CREATE INDEX IF NOT EXISTS idx_reset_user ON password_reset_tokens(user_id,used_at);
CREATE INDEX IF NOT EXISTS idx_orders_workspace_date ON orders(workspace_id,order_date);
CREATE INDEX IF NOT EXISTS idx_insights_workspace ON insights(workspace_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_workspace ON alerts(workspace_id,is_read,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_workspace ON reports(workspace_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sources_workspace ON data_sources(workspace_id);
CREATE INDEX IF NOT EXISTS idx_views_workspace ON saved_views(workspace_id,is_favorite DESC);
