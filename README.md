# InterOps Telemetry API

Minimal, production-safe telemetry ingestion API for InterOps built with Express. Accepts telemetry events over HTTP, stores them in SQLite for quick inspection, and never blocks callers on downstream work.

## Requirements
- Python 3.12+
- Docker (optional)

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 9000
```
The service listens on port **8081** by default. Override with `PORT=<port>` if needed. Telemetry events persist to a local SQLite file at `./telemetry.db` (override with `TELEMETRY_DB_PATH=<path>`).

Starting the service automatically creates `telemetry.db` and the `telemetry_events` table if they do not already exist—no manual migration step is required.

## Run with Docker
```bash
docker build -t interops-telemetry-api .
docker run --rm -p 8081:8081 interops-telemetry-api
```

## Endpoints
- `POST /api/telemetry/events` – accepts telemetry events and returns HTTP 202 immediately (non-blocking)
- `GET /api/telemetry/events` – returns all stored telemetry events as JSON from SQLite
- `GET /health` – basic health probe

## Telemetry payload shape
```json
{
  "eventId": "string",
  "eventType": "string",
  "timestampUtc": "2024-01-01T12:00:00Z",
  "source": "MIRTH",
  "protocol": "HL7v3",
  "interactionId": "PRPA_IN201306UV02",
  "organization": "VA",
  "qhin": "CommonWell",
  "environment": "TEST",
  "status": "SUCCESS",
  "durationMs": 42,
  "resultCount": 1,
  "correlationId": "REQ-123"
}
```

## Example curl commands
Post telemetry (mirrors Mirth HTTP Sender):
```bash
curl -i -X POST http://localhost:8081/api/telemetry/events \
  -H "Content-Type: application/json" \
  -d '{
    "eventId": "evt-001",
    "eventType": "PD_EXECUTION",
    "timestampUtc": "2025-12-26T22:15:00Z",
    "source": "MIRTH",
    "protocol": "HL7v3",
    "interactionId": "PRPA_IN201306UV02",
    "organization": "VA",
    "qhin": "CommonWell",
    "environment": "TEST",
    "status": "SUCCESS",
    "durationMs": 187,
    "resultCount": 1,
    "correlationId": "REQ-123"
  }'
```

Read stored telemetry:
```bash
curl http://localhost:8081/api/telemetry/events
```

If you see an empty array when reading:

- Post your events to the **same host/port** you are reading from (for example, `curl` and browser both pointed at `http://localhost:8081`).
- The SQLite file defaults to `./telemetry.db`. If you override `TELEMETRY_DB_PATH`, ensure the Node process can read/write that location.
- Check the server logs for lines like `[telemetry] returning <n> event(s)` to confirm the backend received your payloads.

## Frontend configuration
If you are viewing the telemetry table in the frontend, ensure it is pointed at the backend you are posting to. The UI defaults to `http://100.27.251.103:8081/api`; when you post events to `localhost`, set `REACT_APP_API_BASE_URL=http://localhost:8081/api`, restart the frontend, and refresh the page so it fetches from your local service.

## Notes
- CORS is enabled for all origins by default.
- Telemetry storage is persisted in SQLite for quick, file-backed testing.
- Ingestion does not block callers; even invalid payloads receive HTTP 202 to avoid retries.
- See `TELEMETRY_DB.md` for the schema and EC2 setup steps.
