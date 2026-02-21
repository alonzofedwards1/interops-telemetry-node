# InterOps Telemetry Node

## Transport endpoint/certificate smoke test

1. Set environment variables:
   - `OPENHIM_API_BASE_URL` (example: `https://localhost:8080`)
   - `OPENHIM_API_USERNAME`
   - `OPENHIM_API_PASSWORD`
   - `OPENHIM_API_VERIFY_TLS` (`false` for dev self-signed certs)
   - `OPENHIM_TLS_HOST` (example: `localhost`)
   - `OPENHIM_TLS_PORT` (example: `5001`)
2. Trigger transport ingestion (push or pull mode):

```bash
curl -X POST http://localhost:8081/api/transport/ingest-openhim \
  -H 'content-type: application/json' \
  -d '{"pull": true}'
```

3. Verify endpoint/certificate/event linkage in Postgres:

```sql
SELECT endpoint_id, scheme, host, port
FROM endpoints
WHERE scheme = 'https'
  AND host = '<OPENHIM_TLS_HOST>'
  AND port = <OPENHIM_TLS_PORT>;

SELECT cert_id, fingerprint_sha1, subject_cn, last_seen_at
FROM certificates
ORDER BY last_seen_at DESC
LIMIT 5;

SELECT id, endpoint_id, cert_id, source, observed_at
FROM endpoint_cert_observations
ORDER BY observed_at DESC
LIMIT 5;

SELECT transaction_id, endpoint_id, cert_id, request_url
FROM transport_events
ORDER BY timestamp DESC
LIMIT 20;
```

4. Optional backfill for historical TLS events:

```bash
python -m app.scripts.backfill_transport_endpoint_cert
```
