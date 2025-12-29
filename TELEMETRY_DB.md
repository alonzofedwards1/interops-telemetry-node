# Telemetry SQLite schema (test-ready)

This service now persists telemetry events to SQLite. Simply start the service (`npm start`) and it will create `telemetry.db` and the `telemetry_events` table if they are missing. Use the schema below only if you want to pre-create the table manually on your EC2 instance.

## Schema
```sql
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
);
```

`raw_payload` stores the full JSON body so the API can return the exact events you POST. The other columns break out commonly needed fields for quick querying.

## Steps to create the DB on an EC2 instance
> These commands assume Amazon Linux 2023/2 or Ubuntu on EC2 and that your code lives in `~/interops-telemetry-api`.

1) Install sqlite3 CLI (choose the command for your distro):
   - Amazon Linux: `sudo yum install -y sqlite`
   - Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y sqlite3`

2) Move into the project directory where the Node service will run:
   ```bash
   cd ~/interops-telemetry-api
   ```

3) Create the schema file and database:
   ```bash
   cat > telemetry_schema.sql <<'SQL'
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
   );
   SQL

   sqlite3 telemetry.db < telemetry_schema.sql
   ```

4) Point the service at the database file (optional—defaults to `./telemetry.db` in the working directory):
   ```bash
   export TELEMETRY_DB_PATH="$(pwd)/telemetry.db"
   ```

5) Start the API:
   ```bash
   npm install
   npm start
   ```

6) Verify the table exists:
   ```bash
   sqlite3 "$TELEMETRY_DB_PATH" ".schema telemetry_events"
   ```

The Node server will also create `telemetry.db` and the `telemetry_events` table automatically on startup if they do not exist; running the SQL above just prepares it ahead of time.
