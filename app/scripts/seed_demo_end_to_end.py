import sqlite3
import uuid
import random
from datetime import datetime, timedelta, timezone

# ============================================================
# CONFIG
# ============================================================

DB_PATH = r"C:\Users\alonz\Documents\interops-telemetry-api\app\db\telemetry.db"

ORG_COUNT = 20
LOGICAL_EXECUTIONS = 50_000
MAX_ATTEMPTS = 5
FINDING_RATE = 0.25
DAYS_BACK = 60

random.seed(42)

# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now(timezone.utc)

def iso(dt):
    return dt.isoformat()

def tune_sqlite(conn):
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-128000;")

# ============================================================
# CLEAR TABLES (DETERMINISTIC RESET)
# ============================================================

TABLES = [
    "findings",
    "pd_executions",
    "telemetry_events",
    "organization_oids",
    "oid_directory",
    "organizations",
]

def clear_tables(conn):
    cur = conn.cursor()
    for t in TABLES:
        cur.execute(f"DELETE FROM {t}")
    conn.commit()

# ============================================================
# ORGS + OIDS
# ============================================================

def generate_oid():
    return f"2.16.840.1.113883.3.{random.randint(100,999)}.{random.randint(1,999)}"

def seed_organizations(cur):
    oids = []

    for i in range(ORG_COUNT):
        org_id = str(uuid.uuid4())
        oid = generate_oid()
        oids.append(oid)

        cur.execute("""
            INSERT INTO organizations (
                id, legal_name, display_name, organization_type,
                primary_oid, qhin_name, hie_name, state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            org_id,
            f"Demo Health Org {i+1}",
            f"DemoOrg {i+1}",
            random.choice(["Hospital", "Health System", "HIE"]),
            oid,
            random.choice(["CommonWell", "eHealthExchange"]),
            random.choice(["Carequality", "Epic", "CRISP"]),
            random.choice(["TX", "CA", "NY", "FL", "VA"]),
        ))

        cur.execute("""
            INSERT INTO oid_directory (
                oid, organization_name, organization_type,
                qhin_name, hie_name, status,
                confidence_score, first_seen_at, last_seen_at
            ) VALUES (?, ?, 'Hospital', 'CommonWell', 'Carequality',
                     'approved', ?, ?, ?)
        """, (
            oid,
            f"DemoOrg {i+1}",
            round(random.uniform(0.7, 0.95), 2),
            iso(now()),
            iso(now()),
        ))

        cur.execute("""
            INSERT INTO organization_oids (
                organization_id, oid, role, environment
            ) VALUES (?, ?, 'owner', 'prod')
        """, (org_id, oid))

    return oids

# ============================================================
# TELEMETRY INGESTION (ONLY DIRECT WRITES)
# ============================================================

def seed_pd_telemetry(cur, oids):
    for _ in range(LOGICAL_EXECUTIONS):
        correlation_id = str(uuid.uuid4())
        attempts = random.randint(1, MAX_ATTEMPTS)

        base_time = now() - timedelta(
            days=random.randint(0, DAYS_BACK),
            seconds=random.randint(0, 86400)
        )

        for attempt in range(attempts):
            ts = base_time + timedelta(seconds=attempt * random.randint(2, 6))
            is_last = attempt == attempts - 1

            transport_ok = is_last and random.random() > 0.1

            # ---------------- TRANSPORT EVENT ----------------
            cur.execute("""
                INSERT INTO telemetry_events (
                    event_id, event_type, event_layer, event_subtype,
                    timestamp_utc, organization, qhin, environment,
                    status, duration_ms, correlation_request_id,
                    protocol_standard, protocol_interaction_id,
                    raw_payload, received_at
                ) VALUES (?, 'PD', 'TRANSPORT', ?, ?, ?, ?, ?, ?, ?, ?, 'HL7', 'ITI-55', ?, ?)
            """, (
                str(uuid.uuid4()),
                "OK" if transport_ok else "TIMEOUT",
                iso(ts),
                random.choice(oids),
                random.choice(["CommonWell", "eHealthExchange"]),
                random.choice(["prod", "stage"]),
                "OK" if transport_ok else "TIMEOUT",
                random.randint(100, 1200),
                correlation_id,
                "<transport/>",
                iso(now()),
            ))

            if not transport_ok:
                continue

            # ---------------- APPLICATION EVENT ----------------
            response = random.choices(
                ["SUCCESS", "PNF", "ERROR"],
                weights=[0.7, 0.2, 0.1]
            )[0]

            missing = None
            error = None

            if response != "SUCCESS" and random.random() < 0.25:
                missing = random.choice(["livingSubjectId", "patientIdentifier"])
                error = "MISSING_REQUIRED_ELEMENT"

            cur.execute("""
                INSERT INTO telemetry_events (
                    event_id, event_type, event_layer, event_subtype,
                    timestamp_utc, organization, qhin, environment,
                    status, duration_ms, correlation_request_id,
                    xml_parse_status, pd_response_code,
                    pd_error_code, missing_required_elements,
                    protocol_standard, protocol_interaction_id,
                    raw_payload, received_at
                ) VALUES (?, 'PD', 'APPLICATION', 'PD_RESPONSE_XML',
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'HL7', 'ITI-55', ?, ?)
            """, (
                str(uuid.uuid4()),
                iso(ts + timedelta(milliseconds=random.randint(200, 4000))),
                random.choice(oids),
                random.choice(["CommonWell", "eHealthExchange"]),
                random.choice(["prod", "stage"]),
                "OK" if response == "SUCCESS" else "ERROR",
                random.randint(200, 4000),
                correlation_id,
                "PARSED",
                response,
                error,
                missing,
                "<HL7_PD_RESPONSE/>",
                iso(now()),
            ))

# ============================================================
# MATERIALIZER: telemetry_events → pd_executions
# ============================================================

def materialize_pd_executions(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            correlation_request_id,
            MIN(timestamp_utc),
            MAX(timestamp_utc),
            COUNT(*),
            MAX(pd_response_code),
            MAX(pd_error_code)
        FROM telemetry_events
        WHERE event_type='PD'
        GROUP BY correlation_request_id
    """)

    for req_id, start, end, count, resp, err in cur.fetchall():
        outcome = "success" if resp == "SUCCESS" else "failure"

        cur.execute("""
            INSERT OR IGNORE INTO pd_executions (
                request_id, transaction_type, direction,
                started_at, completed_at, duration_ms,
                outcome, event_count, root_cause,
                failure_stage, http_status, retry_count, created_at
            ) VALUES (?, 'PD', 'outbound', ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            req_id,
            start,
            end,
            random.randint(300, 6000),
            outcome,
            count,
            err or ("PNF" if resp == "PNF" else None),
            "APPLICATION" if resp else "NETWORK",
            200 if resp else 504,
            max(0, count - 1),
        ))

    conn.commit()

# ============================================================
# RULES ENGINE → FINDINGS (ONLY LEGAL WRITER)
# ============================================================

def evaluate_findings(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT request_id, root_cause, failure_stage
        FROM pd_executions
        WHERE outcome='failure'
    """)

    for request_id, root_cause, stage in cur.fetchall():

        if random.random() > FINDING_RATE:
            continue

        if root_cause == "MISSING_REQUIRED_ELEMENT":
            severity = "critical"
            summary = "Missing required HL7 element"
            detail = "Required patient identity element missing; patient match cannot succeed."
            action = "Update PD request to include required HL7 identifiers."
        elif root_cause == "PNF":
            severity = "warning"
            summary = "Patient Not Found returned"
            detail = "PNF returned by responder; may be valid or due to identifier quality."
            action = "Verify demographics and identifier formatting."
        else:
            severity = "critical"
            summary = "Transport-level PD failure"
            detail = "PD attempt failed before successful application exchange."
            action = "Inspect network, TLS, and endpoint availability."

        cur.execute("""
            INSERT INTO findings (
                id, execution_id, execution_type,
                severity, category, summary,
                technical_detail, recommended_action,
                status, first_seen_at, last_seen_at, created_at
            ) VALUES (?, ?, 'PD', ?, 'Patient Discovery',
                      ?, ?, ?, 'open', ?, ?, CURRENT_TIMESTAMP)
        """, (
            str(uuid.uuid4()),
            request_id,
            severity,
            summary,
            detail,
            action,
            iso(now()),
            iso(now()),
        ))

    conn.commit()

# ============================================================
# MAIN
# ============================================================

def main():
    print("🚀 Telemetry-first seed (correct architecture)")

    conn = sqlite3.connect(DB_PATH, timeout=60)
    tune_sqlite(conn)
    cur = conn.cursor()

    clear_tables(conn)
    print("🧹 Tables cleared")

    oids = seed_organizations(cur)
    conn.commit()
    print(f"🏥 {ORG_COUNT} orgs seeded")

    seed_pd_telemetry(cur, oids)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM telemetry_events")
    print(f"🛰️ telemetry_events: {cur.fetchone()[0]:,}")

    materialize_pd_executions(conn)
    cur.execute("SELECT COUNT(*) FROM pd_executions")
    print(f"🧱 pd_executions: {cur.fetchone()[0]:,}")

    evaluate_findings(conn)
    cur.execute("SELECT COUNT(*) FROM findings")
    print(f"🚨 findings: {cur.fetchone()[0]:,}")

    conn.close()
    print("✅ Seed complete")

if __name__ == "__main__":
    main()
