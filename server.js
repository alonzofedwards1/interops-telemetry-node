const crypto = require('crypto');
const express = require('express');
const cors = require('cors');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

// Basic Express app setup
const app = express();
const port = process.env.PORT || 8081;
const sessionTtlSeconds = Number.parseInt(process.env.AUTH_SESSION_TTL_SECONDS || '43200', 10);
const authCookieName = process.env.AUTH_COOKIE_NAME || 'telemetry_auth';
const authPasswordSalt = process.env.AUTH_PASSWORD_SALT || '';
const authCookieSecure =
  process.env.AUTH_COOKIE_SECURE === 'true' ? true : process.env.NODE_ENV === 'production';
const allowedOrigins = (process.env.CORS_ORIGIN || '')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);

app.use(
  cors({
    origin(origin, callback) {
      if (!origin) {
        callback(null, true);
        return;
      }
      if (allowedOrigins.length === 0 || allowedOrigins.includes(origin)) {
        callback(null, true);
        return;
      }
      callback(new Error(`Origin ${origin} not allowed by CORS`));
    },
    credentials: true,
  }),
);
app.use(express.json({ limit: '1mb' }));

// SQLite setup
const dbPath = process.env.TELEMETRY_DB_PATH || path.join(process.cwd(), 'telemetry.db');
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('[telemetry] failed to connect to sqlite database', err);
  } else {
    console.log(`[telemetry] connected to sqlite database at ${dbPath}`);
  }
});

db.serialize(() => {
  db.run(
    `CREATE TABLE IF NOT EXISTS telemetry_events (
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
    )`,
    (err) => {
      if (err) {
        console.error('[telemetry] failed to ensure telemetry_events table', err);
      } else {
        console.log('[telemetry] ensured telemetry_events table (auto-created if missing)');
      }
    },
  );
  db.run(
    `CREATE TABLE IF NOT EXISTS telemetry_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      token_hash TEXT NOT NULL,
      user_id INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )`,
    (err) => {
      if (err) {
        console.error('[telemetry] failed to ensure telemetry_sessions table', err);
      } else {
        console.log('[telemetry] ensured telemetry_sessions table (auto-created if missing)');
      }
    },
  );
  db.run(
    `CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now'))
    )`,
    (err) => {
      if (err) {
        console.error('[telemetry] failed to ensure users table', err);
      } else {
        console.log('[telemetry] ensured users table (auto-created if missing)');
      }
    },
  );
  db.run(
    'CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON telemetry_sessions(token_hash)',
    (err) => {
      if (err) {
        console.error('[telemetry] failed to ensure session token hash index', err);
      }
    },
  );
  db.run(
    'CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON telemetry_sessions(expires_at)',
    (err) => {
      if (err) {
        console.error('[telemetry] failed to ensure session expiry index', err);
      }
    },
  );
});

function parseCookies(cookieHeader) {
  if (!cookieHeader) return {};
  return cookieHeader.split(';').reduce((accumulator, chunk) => {
    const [rawKey, ...rawValue] = chunk.trim().split('=');
    if (!rawKey) return accumulator;
    const value = rawValue.join('=');
    accumulator[rawKey] = decodeURIComponent(value);
    return accumulator;
  }, {});
}

function hashToken(token) {
  return crypto.createHash('sha256').update(token).digest('hex');
}

function hashPassword(password) {
  return crypto.createHash('sha256').update(`${authPasswordSalt}:${password}`).digest('hex');
}

function issueSession(userId, callback) {
  const token = crypto.randomBytes(32).toString('hex');
  const tokenHash = hashToken(token);
  const expiresAt = Math.floor(Date.now() / 1000) + sessionTtlSeconds;

  db.run(
    'INSERT INTO telemetry_sessions (token_hash, user_id, expires_at) VALUES (?,?,?)',
    [tokenHash, userId, expiresAt],
    (err) => {
      if (err) {
        callback(err);
        return;
      }
      callback(null, token, expiresAt);
    },
  );
}

function clearSession(token, callback) {
  if (!token) {
    callback(null);
    return;
  }
  db.run('DELETE FROM telemetry_sessions WHERE token_hash = ?', [hashToken(token)], (err) => {
    callback(err || null);
  });
}

function requireAuth(req, res, next) {
  const cookies = parseCookies(req.headers.cookie);
  const token = cookies[authCookieName];

  if (!token) {
    res.status(401).json({ error: 'Authentication required.' });
    return;
  }

  const tokenHash = hashToken(token);
  db.get(
    "SELECT user_id, expires_at FROM telemetry_sessions WHERE token_hash = ? AND expires_at > strftime('%s','now')",
    [tokenHash],
    (err, row) => {
      if (err) {
        console.error('[telemetry] auth lookup failed', err);
        res.status(500).json({ error: 'Failed to validate session.' });
        return;
      }
      if (!row) {
        res.status(401).json({ error: 'Invalid or expired session.' });
        return;
      }
      req.user = { userId: row.user_id };
      next();
    },
  );
}

function isValidTelemetry(event) {
  if (!event || typeof event !== 'object') return false;
  const { eventId, eventType } = event;
  return typeof eventId === 'string' && eventId.length > 0 && typeof eventType === 'string' && eventType.length > 0;
}

function storeTelemetryEvent(payload) {
  const source = payload?.source || {};
  const correlation = payload?.correlation || {};
  const execution = payload?.execution || {};
  const outcome = payload?.outcome || {};
  const protocol = payload?.protocol || {};

  const eventId = typeof payload.eventId === 'string' ? payload.eventId : null;
  const eventType = typeof payload.eventType === 'string' ? payload.eventType : null;
  const timestampUtc =
    typeof payload.timestampUtc === 'string'
      ? payload.timestampUtc
      : typeof payload.timestamp === 'string'
        ? payload.timestamp
        : null;

  const sourceSystem =
    typeof source.system === 'string'
      ? source.system
      : typeof payload.source === 'string'
        ? payload.source
        : null;
  const sourceChannelId = typeof source.channelId === 'string' ? source.channelId : null;
  const sourceEnvironment = typeof source.environment === 'string' ? source.environment : null;
  const organization = typeof payload.organization === 'string' ? payload.organization : null;
  const qhin = typeof payload.qhin === 'string' ? payload.qhin : null;
  const environment = typeof payload.environment === 'string' ? payload.environment : null;
  const status =
    typeof outcome.status === 'string'
      ? outcome.status
      : typeof payload.status === 'string'
        ? payload.status
        : null;
  const durationMs =
    typeof execution.durationMs === 'number'
      ? execution.durationMs
      : typeof payload.durationMs === 'number'
        ? payload.durationMs
        : null;
  const resultCount =
    typeof outcome.resultCount === 'number'
      ? outcome.resultCount
      : typeof payload.resultCount === 'number'
        ? payload.resultCount
        : null;
  const correlationId = typeof payload.correlationId === 'string' ? payload.correlationId : null;
  const correlationRequestId = typeof correlation.requestId === 'string' ? correlation.requestId : null;
  const correlationMessageId = typeof correlation.messageId === 'string' ? correlation.messageId : null;
  const protocolStandard =
    typeof protocol.standard === 'string'
      ? protocol.standard
      : typeof payload.protocol === 'string'
        ? payload.protocol
        : null;
  const protocolInteractionId =
    typeof protocol.interactionId === 'string'
      ? protocol.interactionId
      : typeof payload.interactionId === 'string'
        ? payload.interactionId
        : null;

  const rawPayload = JSON.stringify(payload ?? {});

  db.run(
    `INSERT INTO telemetry_events (
      event_id,
      event_type,
      timestamp_utc,
      source_system,
      source_channel_id,
      source_environment,
      organization,
      qhin,
      environment,
      status,
      duration_ms,
      result_count,
      correlation_id,
      correlation_request_id,
      correlation_message_id,
      protocol_standard,
      protocol_interaction_id,
      raw_payload
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
    [
      eventId,
      eventType,
      timestampUtc,
      sourceSystem,
      sourceChannelId,
      sourceEnvironment,
      organization,
      qhin,
      environment,
      status,
      durationMs,
      resultCount,
      correlationId,
      correlationRequestId,
      correlationMessageId,
      protocolStandard,
      protocolInteractionId,
      rawPayload,
    ],
    (err) => {
      if (err) {
        console.error('[telemetry] failed to persist telemetry event', err);
      } else {
        console.log(`[telemetry] stored event ${eventId || 'unknown-id'}`);
      }
    },
  );
}

// Telemetry ingestion (non-blocking, always returns 202)
app.post('/api/telemetry/events', requireAuth, (req, res) => {
  try {
    const payload = req.body || {};
    const eventId = typeof payload.eventId === 'string' ? payload.eventId : 'unknown-id';

    if (isValidTelemetry(payload)) {
      storeTelemetryEvent(payload);
      console.log(`[telemetry] received event ${eventId}`);
    } else {
      console.warn(`[telemetry] invalid telemetry payload received (eventId=${eventId})`);
    }
  } catch (err) {
    console.error('[telemetry] error handling telemetry payload', err);
  }

  res.sendStatus(202);
});

// Telemetry read endpoint
app.get('/api/telemetry/events', requireAuth, (_req, res) => {
  try {
    db.all('SELECT raw_payload FROM telemetry_events ORDER BY id ASC', (err, rows) => {
      if (err) {
        console.error('[telemetry] error reading telemetry store', err);
        res.json([]);
        return;
      }

      const events = rows.map((row) => {
        try {
          return JSON.parse(row.raw_payload);
        } catch (_parseErr) {
          return { raw_payload: row.raw_payload };
        }
      });

      console.log(`[telemetry] returning ${events.length} event(s)`);
      res.json(events);
    });
  } catch (err) {
    console.error('[telemetry] error reading telemetry store', err);
    res.json([]);
  }
});

app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body || {};
  if (typeof username !== 'string' || typeof password !== 'string') {
    res.status(400).json({ error: 'Username and password are required.' });
    return;
  }

  db.get('SELECT id, password_hash FROM users WHERE username = ?', [username], (err, row) => {
    if (err) {
      console.error('[telemetry] failed to lookup user', err);
      res.status(500).json({ error: 'Failed to authenticate.' });
      return;
    }
    if (!row) {
      res.status(401).json({ error: 'Invalid credentials.' });
      return;
    }

    const providedHash = hashPassword(password);
    const isPasswordMatch =
      row.password_hash.length === providedHash.length &&
      crypto.timingSafeEqual(Buffer.from(row.password_hash), Buffer.from(providedHash));

    if (!isPasswordMatch) {
      res.status(401).json({ error: 'Invalid credentials.' });
      return;
    }

    issueSession(row.id, (sessionErr, token, expiresAt) => {
      if (sessionErr) {
        console.error('[telemetry] failed to issue session', sessionErr);
        res.status(500).json({ error: 'Failed to create session.' });
        return;
      }

      res.cookie(authCookieName, token, {
        httpOnly: true,
        secure: authCookieSecure,
        sameSite: 'lax',
        maxAge: sessionTtlSeconds * 1000,
      });
      res.json({ username, expiresAt });
    });
  });
});

app.post('/api/auth/logout', requireAuth, (req, res) => {
  const cookies = parseCookies(req.headers.cookie);
  const token = cookies[authCookieName];
  clearSession(token, (err) => {
    if (err) {
      console.error('[telemetry] failed to clear session', err);
      res.status(500).json({ error: 'Failed to clear session.' });
      return;
    }
    res.clearCookie(authCookieName, {
      httpOnly: true,
      secure: authCookieSecure,
      sameSite: 'lax',
    });
    res.json({ ok: true });
  });
});

app.get('/api/auth/me', requireAuth, (req, res) => {
  res.json({ userId: req.user?.userId });
});

// Simple health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

// Fallback error handler to prevent uncaught exceptions from surfacing
app.use((err, _req, res, _next) => {
  console.error('[telemetry] unhandled error', err);
  res.sendStatus(202);
});

process.on('uncaughtException', (err) => {
  console.error('[telemetry] uncaught exception', err);
});

process.on('unhandledRejection', (reason) => {
  console.error('[telemetry] unhandled rejection', reason);
});

app.listen(port, () => {
  console.log(`Telemetry API listening on port ${port}`);
});
