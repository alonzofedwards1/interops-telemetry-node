# EC2 SQLite setup for telemetry data

These steps show how to SSH into your EC2 instance and create the SQLite database for telemetry events. The service will auto-create the table on startup, but you can pre-create it if you want to inspect the schema beforehand.

## 1) SSH into the instance
Use your key and username for the AMI you launched (e.g., `ec2-user` for Amazon Linux, `ubuntu` for Ubuntu):

```bash
ssh -i /path/to/key.pem ec2-user@<EC2_PUBLIC_IP>
# or for Ubuntu images
ssh -i /path/to/key.pem ubuntu@<EC2_PUBLIC_IP>
```

## 2) Install sqlite3 CLI (if missing)
```bash
# Amazon Linux
sudo yum install -y sqlite

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y sqlite3
```

## 3) Go to the app directory
```bash
cd ~/interops-telemetry-api
```

## 4) (Optional) Pre-create the database and table
The service will create `telemetry.db` automatically. To create it manually for testing:
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

## 5) Start the service (auto-creates the DB if needed)
```bash
npm install
npm start
```

## 6) Verify the table exists
```bash
sqlite3 telemetry.db ".schema telemetry_events"
```

Exit the SSH session with `exit` when you are done.
