-- PostgreSQL schema for InterOps Telemetry + Transport Rules backend.
-- Run this file on the target PostgreSQL database before switching the service.

BEGIN;

CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_layer TEXT,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    source_channel_id TEXT,
    source_environment TEXT,
    status TEXT,
    duration_ms INTEGER,
    correlation_request_id TEXT,
    cert_status TEXT,
    cert_thumbprint TEXT,
    raw_payload JSONB
);

CREATE TABLE IF NOT EXISTS pd_executions (
    request_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    outcome TEXT,
    transaction_type TEXT,
    source_channel_id TEXT,
    source_environment TEXT,
    source_oid TEXT,
    target_oid TEXT,
    cert_status TEXT DEFAULT 'NOT_REPORTED',
    cert_thumbprint TEXT,
    failure_stage TEXT,
    root_cause TEXT,
    http_status INTEGER,
    retry_count INTEGER,
    first_event_id TEXT,
    last_event_id TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telemetry_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    token_hash TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON telemetry_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON telemetry_sessions(expires_at);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    execution_id TEXT,
    execution_type TEXT CHECK (execution_type IN ('PD', 'QD', 'RD')) DEFAULT 'PD',
    severity TEXT CHECK (severity IN ('info', 'warning', 'critical')) NOT NULL,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    technical_detail TEXT,
    recommended_action TEXT,
    status TEXT CHECK (status IN ('open', 'acknowledged', 'resolved')) DEFAULT 'open',
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_execution ON findings(execution_id);
CREATE INDEX IF NOT EXISTS idx_findings_created ON findings(created_at);

CREATE TABLE IF NOT EXISTS oid_directory (
    oid TEXT PRIMARY KEY,
    organization_name TEXT,
    status TEXT CHECK (status IN ('UNKNOWN', 'PENDING', 'ACTIVE', 'DEPRECATED')) DEFAULT 'UNKNOWN',
    confidence_score DOUBLE PRECISION,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_oid_directory_status ON oid_directory(status);
CREATE INDEX IF NOT EXISTS idx_oid_directory_last_seen ON oid_directory(last_seen_at);


CREATE TABLE IF NOT EXISTS endpoints (
    endpoint_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    scheme TEXT NOT NULL,
    service_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_endpoints_scheme_host_port ON endpoints(scheme, host, port);

CREATE TABLE IF NOT EXISTS certificates (
    cert_id BIGSERIAL PRIMARY KEY,
    fingerprint_sha1 TEXT UNIQUE NOT NULL,
    subject_cn TEXT,
    issuer_cn TEXT,
    not_before TIMESTAMPTZ,
    not_after TIMESTAMPTZ,
    pem TEXT,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS endpoint_cert_observations (
    endpoint_id BIGINT NOT NULL REFERENCES endpoints(endpoint_id) ON DELETE CASCADE,
    cert_id BIGINT NOT NULL REFERENCES certificates(cert_id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    source TEXT,
    PRIMARY KEY (endpoint_id, cert_id, observed_at)
);

CREATE TABLE IF NOT EXISTS transport_events (
    id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(128) UNIQUE NOT NULL,
    channel VARCHAR(255) NOT NULL,
    request_method VARCHAR(32) NOT NULL,
    request_url VARCHAR(2048) NOT NULL,
    request_headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_status INTEGER NOT NULL,
    response_duration_ms INTEGER NOT NULL,
    source_ip VARCHAR(64),
    timestamp TIMESTAMPTZ NOT NULL,
    cert_subject_cn VARCHAR(255),
    cert_subject_san TEXT,
    cert_issuer_cn VARCHAR(255),
    cert_not_before TIMESTAMPTZ,
    cert_not_after TIMESTAMPTZ,
    cert_serial VARCHAR(255),
    cert_sha256 VARCHAR(255),
    cert_status VARCHAR(32),
    endpoint_id BIGINT REFERENCES endpoints(endpoint_id),
    cert_id BIGINT REFERENCES certificates(cert_id)
);

CREATE INDEX IF NOT EXISTS idx_transport_events_transaction_id ON transport_events(transaction_id);
CREATE INDEX IF NOT EXISTS idx_transport_events_channel ON transport_events(channel);
CREATE INDEX IF NOT EXISTS idx_transport_events_response_status ON transport_events(response_status);
CREATE INDEX IF NOT EXISTS idx_transport_events_response_duration_ms ON transport_events(response_duration_ms);
CREATE INDEX IF NOT EXISTS idx_transport_events_timestamp ON transport_events(timestamp);


ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_subject_cn VARCHAR(255);
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_subject_san TEXT;
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_issuer_cn VARCHAR(255);
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_not_before TIMESTAMPTZ;
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_not_after TIMESTAMPTZ;
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_serial VARCHAR(255);
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_sha256 VARCHAR(255);
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_status VARCHAR(32);
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS endpoint_id BIGINT;
ALTER TABLE transport_events ADD COLUMN IF NOT EXISTS cert_id BIGINT;


COMMIT;
