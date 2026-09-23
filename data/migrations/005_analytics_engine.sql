CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    event_name TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    revenue REAL NOT NULL DEFAULT 0,
    source TEXT,
    device TEXT,
    region TEXT,
    product TEXT,
    properties_json TEXT NOT NULL DEFAULT '{}',
    import_job_id TEXT REFERENCES import_jobs(id) ON DELETE SET NULL,
    data_source_id INTEGER REFERENCES data_sources(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(workspace_id,event_id)
);

CREATE TABLE IF NOT EXISTS analytics_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    match_type TEXT NOT NULL CHECK (match_type IN ('ALL','ANY')),
    rules_json TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_workspace_time ON analytics_events(workspace_id,occurred_at);
CREATE INDEX IF NOT EXISTS idx_analytics_events_workspace_name_time ON analytics_events(workspace_id,event_name,occurred_at);
CREATE INDEX IF NOT EXISTS idx_analytics_events_workspace_user_time ON analytics_events(workspace_id,user_id,occurred_at);
CREATE INDEX IF NOT EXISTS idx_analytics_events_workspace_session_time ON analytics_events(workspace_id,session_id,occurred_at);
CREATE INDEX IF NOT EXISTS idx_analytics_segments_workspace ON analytics_segments(workspace_id,updated_at DESC);

INSERT OR IGNORE INTO analytics_events
    (workspace_id,event_id,user_id,event_name,occurred_at,revenue,source,region,product,import_job_id,data_source_id,properties_json)
SELECT workspace_id,
       'order:' || id,
       customer_id,
       'purchase',
       order_date,
       amount,
       source,
       region,
       COALESCE(product,category),
       import_job_id,
       data_source_id,
       '{}'
FROM orders;
