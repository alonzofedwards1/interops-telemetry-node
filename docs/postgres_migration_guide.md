# PostgreSQL Migration Guide

If you are migrating away from SQLite to PostgreSQL, apply the schema in:

- `app/db/schema_postgres.sql`

## Tables included (all bases covered)

- `telemetry_events`
- `pd_executions`
- `users`
- `telemetry_sessions`
- `findings`
- `oid_directory`
- `transport_events`

## Why these are included

These tables cover all persisted domains currently present in the repository:

- Core telemetry event storage and PD execution state.
- Auth/session tables used by API authentication.
- Findings and OID registry data.
- New transport-rules ingestion output (`transport_events`).

## Suggested migration sequence

1. Create your PostgreSQL database.
2. Run `app/db/schema_postgres.sql`.
3. Export from SQLite and import data table-by-table.
4. Update app connection config to PostgreSQL URL.
5. Run smoke tests for:
   - auth login/session creation
   - telemetry ingestion and reads
   - findings queries
   - transport ingestion writes

## Notes on types

- SQLite `TEXT` datetime fields were upgraded to `TIMESTAMPTZ` where appropriate.
- `raw_payload` and `request_headers` are stored as `JSONB` in PostgreSQL.
- Integer autoincrement IDs are represented as `BIGSERIAL`.
