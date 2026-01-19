import sqlite3
import uuid
import random
from datetime import datetime, timedelta, timezone
import time

DB_PATH = r"C:\Users\alonz\Documents\interops-telemetry-api\app\db\telemetry.db"

# ============================================================
# Helpers
# ============================================================

def now():
    return datetime.now(timezone.utc).isoformat()

def with_retry(fn, label, retries=5, delay=0.25):
    for attempt in range(retries):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise
            if attempt == retries - 1:
                raise
            print(f"⏳ DB locked while writing {label}, retrying...")
            time.sleep(delay)

# ============================================================
# Wipe tables
# ============================================================

TABLES = [
    "findings",
    "pd_executions",
    "organization_oids",
    "oid_directory",
    "organizations",
]

def clear_tables(conn):
    cursor = conn.cursor()
    for table in TABLES:
        with_retry(
            lambda t=table: cursor.execute(f"DELETE FROM {t};"),
            f"clear {table}",
        )
    conn.commit()

# ============================================================
# Seed Organizations + Primary OIDs
# ============================================================

ORG_STATES = ["TX", "CA", "NY", "FL", "VA"]
ORG_TYPES = ["Hospital", "HIE", "Health System"]

def generate_oid():
    return f"2.16.840.1.113883.3.{random.randint(100,999)}.{random.randint(1,99)}"

def seed_organizations_and_oids(cursor):
    orgs = []
    oids = []

    for i in range(8):
        org_id = str(uuid.uuid4())
        primary_oid = generate_oid()

        legal = f"Demo Health Org {i+1}"
        display = f"DemoOrg {i+1}"
        org_type = random.choice(ORG_TYPES)
        qhin = random.choice(["CommonWell", "eHealthExchange"])
        hie = random.choice(["CRISP", "Epic", "Carequality"])
        state = random.choice(ORG_STATES)

        cursor.execute(
            """
            INSERT INTO organizations (
                id,
                legal_name,
                display_name,
                organization_type,
                primary_oid,
                qhin_name,
                hie_name,
                state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                org_id,
                legal,
                display,
                org_type,
                primary_oid,
                qhin,
                hie,
                state,
            ),
        )

        cursor.execute(
            """
            INSERT INTO oid_directory (
                oid,
                organization_name,
                organization_type,
                qhin_name,
                hie_name,
                status,
                confidence_score,
                first_seen_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                primary_oid,
                display,
                org_type,
                qhin,
                hie,
                "approved",
                round(random.uniform(0.7, 0.95), 2),
                now(),
                now(),
            ),
        )

        cursor.execute(
            """
            INSERT INTO organization_oids (
                organization_id,
                oid,
                role,
                environment
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                org_id,
                primary_oid,
                "owner",
                "prod",
            ),
        )

        orgs.append(org_id)
        oids.append(primary_oid)

    return orgs, oids

# ============================================================
# Seed PD Executions (EXECUTION-INTELLIGENCE READY)
# ============================================================

def seed_pd_executions(cursor, oids, count=40):
    exec_ids = []

    FAILURE_PROFILES = [
        ("CERT_EXPIRED", "TLS", 495),
        ("TIMEOUT", "TRANSPORT", None),
        ("HTTP_ERROR", "APPLICATION", 500),
        ("SCHEMA", "SOAP", 400),
    ]

    for _ in range(count):
        request_id = str(uuid.uuid4())
        started = datetime.now(timezone.utc) - timedelta(seconds=random.randint(1, 60))
        completed = started + timedelta(milliseconds=random.randint(150, 6000))
        duration_ms = int((completed - started).total_seconds() * 1000)

        is_failure = random.random() < 0.25

        if is_failure:
            root_cause, failure_stage, http_status = random.choice(FAILURE_PROFILES)
            outcome = "failure"
            retry_count = random.randint(1, 3)
            cert_thumbprint = (
                f"{random.randint(10,99):X}:{random.randint(10,99):X}:{random.randint(10,99):X}"
                if root_cause == "CERT_EXPIRED"
                else None
            )
        else:
            root_cause = None
            failure_stage = None
            http_status = 200
            outcome = "success"
            retry_count = 0
            cert_thumbprint = None

        cursor.execute(
            """
            INSERT INTO pd_executions (
                request_id,
                transaction_type,
                direction,
                started_at,
                completed_at,
                duration_ms,
                outcome,
                root_cause,
                failure_stage,
                http_status,
                retry_count,
                cert_thumbprint,
                source_environment,
                source_oid,
                target_oid,
                qhin_name,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                "PD",
                random.choice(["inbound", "outbound"]),
                started.isoformat(),
                completed.isoformat(),
                duration_ms,
                outcome,
                root_cause,
                failure_stage,
                http_status,
                retry_count,
                cert_thumbprint,
                random.choice(["prod", "stage"]),
                random.choice(oids),
                random.choice(oids),
                random.choice(["CommonWell", "eHealthExchange"]),
                now(),
            ),
        )

        exec_ids.append(request_id)

    return exec_ids

# ============================================================
# Seed Findings
# ============================================================

SEVERITIES = ["info", "warning", "critical"]
STATUSES = ["open", "resolved", "non-compliant"]

def seed_findings(cursor, exec_ids, oids, count=100):
    for _ in range(count):
        cursor.execute(
            """
            INSERT INTO findings (
                id,
                execution_id,
                execution_type,
                severity,
                category,
                summary,
                technical_detail,
                recommended_action,
                status,
                related_oid,
                first_seen_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                random.choice(exec_ids),
                "PD",
                random.choice(SEVERITIES),
                "Patient Discovery",
                "Patient Discovery anomaly detected",
                "PD execution deviated from expected behavior",
                "Verify demographics and retry",
                random.choice(STATUSES),
                random.choice(oids),
                now(),
                now(),
            ),
        )

# ============================================================
# Main
# ============================================================

def main():
    print("🌱 Seeding demo dataset (execution-intelligence enabled)…")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=OFF;")

    cursor = conn.cursor()

    clear_tables(conn)
    print("🧹 Tables cleared")

    org_ids, oids = seed_organizations_and_oids(cursor)
    print("✅ organizations + primary OIDs")

    exec_ids = seed_pd_executions(cursor, oids)
    print("✅ pd_executions (with root causes)")

    seed_findings(cursor, exec_ids, oids)
    print("✅ findings")

    conn.commit()
    conn.close()

    print("🎉 Seed completed successfully")

if __name__ == "__main__":
    main()
