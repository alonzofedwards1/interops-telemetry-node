# Transport Rules MVP Implementation Plan

This plan prioritizes MVP transport rules engine capabilities without breaking
the current telemetry ingestion flow. It stays within the existing FastAPI
architecture (telemetry ingestion → PD materialization → findings evaluation)
and adds a parallel transport-focused rules pipeline where needed.

---

## Guiding principles

- **No breaking changes to telemetry ingestion**: continue accepting current
  payloads; add optional fields and new tables alongside existing ones.
- **Reuse existing findings machinery**: deterministic IDs + dedupe via the
  existing evaluator/repository patterns.
- **Separate transport from application**: persist transport transaction facts
  independently, then derive findings.

---

## Phased delivery (optimized for MVP)

### Phase 0 — Instrumentation & schema foundation (½–1 day)

1. **Add transport transaction storage**
   - Create a new table (e.g., `transport_transactions`) to store:
     - `correlation_request_id`, `event_id`, `event_type`, `timestamp_utc`
     - `source_channel_id`, `source_environment`
     - `cert_status`, `cert_thumbprint`
     - `transport_status`, `http_status`
     - `source_oid`, `target_oid`, `partner_name` (nullable)
   - Rationale: decouple transport outcomes from PD materialization to support
     transport-only telemetry.

2. **Extend telemetry ingestion (non-breaking)**
   - Parse optional fields from transport events:
     - `transportStatus` / `status`
     - `httpStatus`
     - `sourceOid`, `targetOid`, or `partnerId` (if present)
   - Store these fields in the new transport table while keeping existing
     telemetry_events behavior intact.

**Outcome**: foundational storage for transport facts; no behavior changes.

---

### Phase 1 — MVP Transport findings (1–2 days)

3. **Add transport findings rules**
   - Introduce a `findings.rules.transport` package.
   - Rules to implement:
     - **AC‑T‑001**: expired/invalid/untrusted certificate detection
       - Use `cert_status` or evidence in raw telemetry payloads.
     - **AC‑T‑005**: track transport outcomes and classify failure stage
       - Use transport status + HTTP status; map to SECURITY/TRANSPORT.
     - **AC‑T‑009**: isolate transport root cause from application failures
       - Only use transport transactions; never application-layer data.
   - Each rule emits deterministic IDs based on:
     - partner identifier + root cause + rule version.

4. **Wire transport rules evaluation**
   - Trigger evaluation after transport transaction insert.
   - Reuse existing `findings.evaluator` patterns and repository writes.

**Outcome**: MVP transport findings available with dedupe and severity.

---

### Phase 2 — MVP attribution & dedupe hardening (1–2 days)

5. **AC‑T‑008**: attribute failures to external orgs
   - Prefer explicit `sourceOid`/`targetOid` in telemetry payloads.
   - Fallback to OID extraction from payload if available.
   - Store partner mapping in transport table and resolve names via `oid_directory`.

6. **AC‑T‑006**: prevent duplicate transport findings
   - Ensure deterministic IDs use stable transport signature:
     - `partner_oid + endpoint + root_cause + rule_version`.
   - Leverage existing dedupe logic in findings evaluator.

**Outcome**: transport findings are attributed and de-noised.

---

### Phase 3 — Expiration warning & proactive checks (1–2 weeks)

7. **AC‑T‑002**: certificates approaching expiration
   - Extend telemetry ingestion to accept `certNotAfter` (ISO timestamp).
   - Store `cert_not_after` in transport transactions.
   - Add a warning rule with configurable threshold (e.g., 30 days).

8. **AC‑T‑003**: certificate–private key pairing
   - Requires a gateway/agent to validate pairing and send results.
   - Add an optional `certKeyPairValid` boolean in telemetry payloads.
   - Emit findings when pairing is invalid or unknown.

**Outcome**: full MVP coverage, proactive risk detection.

---

## Minimal API additions (non-breaking)

- No new required request fields for `/api/telemetry/events`.
- New optional fields accepted on transport events:
  - `httpStatus`, `transportStatus`
  - `sourceOid`, `targetOid`, `partnerId`
  - `certNotAfter`, `certKeyPairValid`
- New read-only endpoints:
  - `/api/transport/findings` (optional)
  - `/api/transport/transactions` (optional)

---

## Frontend impact (expected)

**No breaking changes** for existing screens. New transport findings and
transactions would require UI additions if you want to surface them:

- **If you want transport findings in the UI:**
  - Add a filter or tab for `executionType = TRANSPORT`.
  - Update any dashboards relying on findings counts if they should include
    transport categories.
- **If you want certificate health panels:**
  - Add new widgets for expiring/invalid cert counts.
  - Add attribution columns (partner/organization name).

---

## Deliverables checklist

- [ ] Migration for `transport_transactions` table
- [ ] Telemetry ingestion updates (optional fields)
- [ ] Transport rules package + registration
- [ ] Findings evaluator hook for transport rules
- [ ] Optional read endpoints for transport facts/findings
- [ ] Frontend UI updates (if you want transport dashboards)

