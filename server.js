const crypto = require('crypto');
const express = require('express');
const cors = require('cors');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

/* ============================================================
   App / Config
============================================================ */

const app = express();
const port = process.env.PORT || 8081;

const sessionTtlSeconds = Number.parseInt(process.env.AUTH_SESSION_TTL_SECONDS || '43200', 10);
const authCookieName = process.env.AUTH_COOKIE_NAME || 'telemetry_auth';
const authPasswordSalt = process.env.AUTH_PASSWORD_SALT || '';
const authCookieSecure =
  process.env.AUTH_COOKIE_SECURE === 'true' ? true : process.env.NODE_ENV === 'production';

const allowedOrigins = (process.env.CORS_ORIGIN || '')
  .split(',')
  .map((o) => o.trim())
  .filter(Boolean);

/* ============================================================
   Middleware
============================================================ */

app.use(
  cors({
    origin(origin, callback) {
      if (!origin || allowedOrigins.length === 0 || allowedOrigins.includes(origin)) {
        callback(null, true);
      } else {
        callback(new Error(`Origin ${origin} not allowed by CORS`));
      }
    },
    credentials: true,
  }),
);

app.use(express.json({ limit: '1mb' }));

/* ============================================================
   SQLite Setup
============================================================ */

const dbPath = process.env.TELEMETRY_DB_PATH || path.join(process.cwd(), 'telemetry.db');
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('[telemetry] sqlite connection failed', err);
  } else {
    console.log(`[telemetry] connected to sqlite at ${dbPath}`);
  }
});

db.serialize(() => {
  /* ---- Telemetry Events ---- */
  db.run(`
    CREATE TABLE IF NOT EXISTS telemetry_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id TEXT,
      event_type TEXT,
      timestamp_utc TEXT,
      source_system TEXT,
      source_channel_id TEXT,
      source_environment TEXT,
      organization TEXT,
      qhin TEXT,
      environment TEXT,
      status TEXT,
      duration_ms INTEGER,
      result_count INTEGER,
      correlation_id TEXT,
      correlation_request_id TEXT,
      correlation_message_id TEXT,
      protocol_standard TEXT,
      protocol_interaction_id TEXT,
      raw_payload TEXT NOT NULL,
      received_at TEXT DEFAULT (datetime('now'))
    )
  `);

  /* ---- PD Executions (AUTHORITATIVE) ---- */
  db.run(`
    CREATE TABLE IF NOT EXISTS pd_executions (
      id TEXT PRIMARY KEY,
      request_id TEXT NOT NULL,
      qhin TEXT NOT NULL,
      direction TEXT NOT NULL,
      outcome TEXT NOT NULL,
      root_cause TEXT,
      cert_thumbprint TEXT,
      duration_ms INTEGER,
      started_at TEXT NOT NULL,
      environment TEXT NOT NULL
    )
  `);

  /* ---- Users / Sessions ---- */
  db.run(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now'))
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS telemetry_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      token_hash TEXT NOT NULL,
      user_id INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
  `);

  db.run(`CREATE INDEX IF NOT EXISTS idx_pd_exec_outcome ON pd_executions(outcome)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_pd_exec_root ON pd_executions(root_cause)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_pd_exec_qhin ON pd_executions(qhin)`);
});

/* ============================================================
   Auth Helpers
============================================================ */

function parseCookies(header) {
  if (!header) return {};
  return header.split(';').reduce((acc, c) => {
    const [k, ...v] = c.trim().split('=');
    acc[k] = decodeURIComponent(v.join('='));
    return acc;
  }, {});
}

function hashToken(token) {
  return crypto.createHash('sha256').update(token).digest('hex');
}

function hashPassword(password) {
  return crypto.createHash('sha256').update(`${authPasswordSalt}:${password}`).digest('hex');
}

function requireAuth(req, res, next) {
  const token = parseCookies(req.headers.cookie)[authCookieName];
  if (!token) return res.status(401).json({ error: 'Auth required' });

  db.get(
    `SELECT user_id FROM telemetry_sessions
     WHERE token_hash = ? AND expires_at > strftime('%s','now')`,
    [hashToken(token)],
    (err, row) => {
      if (err || !row) return res.status(401).json({ error: 'Invalid session' });
      req.user = row.user_id;
      next();
    },
  );
}

/* ============================================================
   Telemetry Ingest (RAW EVENTS)
============================================================ */

app.post('/api/telemetry/events', requireAuth, (req, res) => {
  const payload = req.body ?? {};
  db.run(
    `
    INSERT INTO telemetry_events (
      event_id, event_type, timestamp_utc, organization, qhin,
      environment, status, duration_ms, correlation_request_id, raw_payload
    ) VALUES (?,?,?,?,?,?,?,?,?,?)
    `,
    [
      payload.eventId ?? null,
      payload.eventType ?? null,
      payload.timestampUtc ?? null,
      payload.organization ?? null,
      payload.qhin ?? null,
      payload.environment ?? null,
      payload.status ?? null,
      payload.durationMs ?? null,
      payload.correlation?.requestId ?? null,
      JSON.stringify(payload),
    ],
  );

  res.sendStatus(202);
});

/* ============================================================
   PD Execution Materialization (EXAMPLE)
============================================================ */

app.post('/api/pd-executions', requireAuth, (req, res) => {
  const exec = req.body;

  db.run(
    `
    INSERT INTO pd_executions (
      id, request_id, qhin, direction, outcome,
      root_cause, cert_thumbprint, duration_ms,
      started_at, environment
    ) VALUES (?,?,?,?,?,?,?,?,?,?)
    `,
    [
      exec.id,
      exec.requestId,
      exec.qhin,
      exec.direction,
      exec.outcome,
      exec.rootCause ?? null,
      exec.certThumbprint ?? null,
      exec.durationMs ?? null,
      exec.startedAt,
      exec.environment,
    ],
    (err) => {
      if (err) {
        console.error('[pd-exec] insert failed', err);
        return res.status(500).json({ error: 'Failed to store execution' });
      }
      res.json({ ok: true });
    },
  );
});

/* ============================================================
   INTEGRATION HEALTH (NO MOCK DATA)
============================================================ */

app.get('/api/health/integrations', (_req, res) => {
  const sql = `
    SELECT
      COUNT(*) AS totalExecutions,
      SUM(CASE WHEN LOWER(outcome) = 'success' THEN 1 ELSE 0 END) AS successExecutions,
      COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN cert_thumbprint END) AS expiredCerts,
      COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN qhin END) AS affectedPartners
    FROM pd_executions
  `;

  db.get(sql, (err, row) => {
    if (err) {
      console.error('[health] query failed', err);
      return res.status(500).json({ error: 'Health query failed' });
    }

    const total = Number(row.totalExecutions || 0);
    const success = Number(row.successExecutions || 0);

    res.json({
      totalExecutions: total,
      successRate: total > 0 ? Math.round((success / total) * 100) : 0,
      certificateHealth: {
        expired: Number(row.expiredCerts || 0),
        expiringSoon: 0,
        valid: null,
      },
      affectedPartners: Number(row.affectedPartners || 0),
    });
  });
});

/* ============================================================
   Health / Boot
============================================================ */

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.listen(port, () => {
  console.log(`Telemetry API listening on ${port}`);
});
