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
# Wipe tables (users + sessions preserved)
# ============================================================

TABLES = [
    "findings",
    "pd_executions",
    "organization_oids",
    "oid_directory",
    "organizations",
]

def clear_tables(conn):
    cur = conn.cursor()
    for table in TABLES:
        with_retry(lambda t=table: cur.execute(f"DELETE FROM {t};"), f"clear {table}")
    conn.commit()

# ============================================================
# Seed Organizations + OIDs
# ============================================================

ORG_STATES = ["TX", "CA", "NY", "FL", "VA"]
ORG_TYPES = ["Hospital", "HIE", "Health System"]

def generate_oid():
    return f"2.16.840.1.113883.3.{random.randint(100,999)}.{random.randint(1,99)}"

def seed_organizations_and_oids(cur):
    org_ids = []
    oids = []

    for i in range(8):
        org_id = str(uuid.uuid4())
        oid = generate_oid()

        org_type = random.choice(ORG_TYPES)
        qhin = random.choice(["CommonWell", "eHealthExchange"])
        hie = random.choice(["CRISP", "Epic", "Carequality"])
        state = random.choice(ORG_STATES)

        legal_name = f"Demo Health Org {i+1}"
        display_name = f"DemoOrg {i+1}"

        # organizations
        cur.execute("""
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
        """, (
            org_id,
            legal_name,
            display_name,
            org_type,
            oid,
            qhin,
            hie,
            state,
        ))

        # oid_directory
        cur.execute("""
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
        """, (
            oid,
            display_name,
            org_type,
            qhin,
            hie,
            "approved",
            round(random.uniform(0.75, 0.95), 2),
            now(),
            now(),
        ))

        # organization_oids
        cur.execute("""
            INSERT INTO organization_oids (
                organization_id,
                oid,
                role,
                environment
            )
            VALUES (?, ?, 'owner', 'prod')
        """, (org_id, oid))

        org_ids.append(org_id)
        oids.append(oid)

    return org_ids, oids

# ============================================================
# Seed PD Executions (CERT-AWARE)
# ============================================================

CERT_STATUSES = ["VALID", "EXPIRING_SOON", "EXPIRED"]

FAILURE_PROFILE = {
    "EXPIRED": ("CERT_EXPIRED", "TLS", 495),
}

def seed_pd_executions(cur, oids, count=40):
    exec_ids = []

    for _ in range(count):
        request_id = str(uuid.uuid4())

        cert_status = random.choices(
            CERT_STATUSES,
            weights=[0.65, 0.20, 0.15]
        )[0]

        started = datetime.now(timezone.utc) - timedelta(seconds=random.randint(1, 90))
        completed = started + timedelta(milliseconds=random.randint(200, 6000))
        duration_ms = int((completed - started).total_seconds() * 1000)

        cert_thumbprint = (
            f"{random.randint(10,99):X}:{random.randint(10,99):X}:{random.randint(10,99):X}"
        )

        if cert_status == "EXPIRED":
            outcome = "failure"
            root_cause, stage, http_status = FAILURE_PROFILE["EXPIRED"]
            retry_count = random.randint(1, 3)
        else:
            outcome = "success"
            root_cause = None
            stage = None
            http_status = 200
            retry_count = 0

        cur.execute("""
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
                cert_status,
                source_environment,
                source_oid,
                target_oid,
                qhin_name,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            "PD",
            random.choice(["inbound", "outbound"]),
            started.isoformat(),
            completed.isoformat(),
            duration_ms,
            outcome,
            root_cause,
            stage,
            http_status,
            retry_count,
            cert_thumbprint,
            cert_status,
            random.choice(["prod", "stage"]),
            random.choice(oids),
            random.choice(oids),
            random.choice(["CommonWell", "eHealthExchange"]),
            now(),
        ))

        exec_ids.append(request_id)

    return exec_ids

# ============================================================
# Seed Findings (Execution-Correlated)
# ============================================================

SEVERITIES = ["info", "warning", "critical"]
STATUSES = ["open", "resolved", "non-compliant"]

def seed_findings(cur, exec_ids, oids, count=100):
    for _ in range(count):
        cur.execute("""
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
        """, (
            str(uuid.uuid4()),
            random.choice(exec_ids),
            "PD",
            random.choice(SEVERITIES),
            "Patient Discovery",
            "PD anomaly detected",
            "Observed deviation during PD execution",
            "Review demographics or retry transaction",
            random.choice(STATUSES),
            random.choice(oids),
            now(),
            now(),
        ))

# ============================================================
# Main
# ============================================================

def main():
    print("🌱 Rebuilding execution-intelligence dataset...")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=OFF;")

    cur = conn.cursor()

    clear_tables(conn)
    print("🧹 Tables cleared")

    org_ids, oids = seed_organizations_and_oids(cur)
    print("✅ Organizations + OID Directory")

    exec_ids = seed_pd_executions(cur, oids)
    print("✅ PD Executions (cert-aware)")

    seed_findings(cur, exec_ids, oids)
    print("✅ Findings")

    conn.commit()
    conn.close()

    print("🎉 Dataset ready for integration health + cert analytics")

if __name__ == "__main__":
    main()
