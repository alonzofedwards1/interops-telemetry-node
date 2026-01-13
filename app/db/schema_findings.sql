CREATE TABLE IF NOT EXISTS findings (
  id TEXT PRIMARY KEY,
  execution_id TEXT,
  execution_type TEXT CHECK (execution_type IN ('PD','QD','RD')) DEFAULT 'PD',
  severity TEXT CHECK (severity IN ('info','warning','critical')) NOT NULL,
  category TEXT NOT NULL,
  summary TEXT NOT NULL,
  technical_detail TEXT,
  recommended_action TEXT,
  status TEXT CHECK (status IN ('open','acknowledged','resolved')) DEFAULT 'open',
  first_seen_at TEXT,
  last_seen_at TEXT,
  created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_execution ON findings(execution_id);
CREATE INDEX IF NOT EXISTS idx_findings_created ON findings(created_at);
