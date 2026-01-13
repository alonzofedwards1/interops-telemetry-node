CREATE TABLE IF NOT EXISTS oid_directory (
  oid TEXT PRIMARY KEY,
  organization_name TEXT,
  status TEXT CHECK (status IN ('UNKNOWN','PENDING','ACTIVE','DEPRECATED')) DEFAULT 'UNKNOWN',
  confidence_score REAL,
  first_seen_at TEXT,
  last_seen_at TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_oid_directory_status ON oid_directory(status);
CREATE INDEX IF NOT EXISTS idx_oid_directory_last_seen ON oid_directory(last_seen_at);
