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
# Seed Organizations + Primary OIDs (CORRECT ORDER)
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

        # ---- organizations (PRIMARY OID SET HERE) ----
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

        # ---- oid_directory ----
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

        # ---- organization_oids ----
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
# Seed PD Executions
# ============================================================

def seed_pd_executions(cursor, oids, count=40):
    exec_ids = []

    for _ in range(count):
        request_id = str(uuid.uuid4())
        started = datetime.now(timezone.utc) - timedelta(seconds=random.randint(1, 5))
        completed = started + timedelta(milliseconds=random.randint(150, 3000))

        cursor.execute(
            """
            INSERT INTO pd_executions (
                request_id,
                started_at,
                completed_at,
                duration_ms,
                outcome,
                source_oid,
                target_oid,
                qhin_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                started.isoformat(),
                completed.isoformat(),
                int((completed - started).total_seconds() * 1000),
                random.choice(["success", "failure"]),
                random.choice(oids),
                random.choice(oids),
                random.choice(["CommonWell", "eHealthExchange"]),
            ),
        )

        exec_ids.append(request_id)

    return exec_ids

# ============================================================
# Seed Findings (JOIN-SAFE)
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
                "PD response did not meet expected behavior",
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
    print("🌱 Seeding demo dataset (authoritative, schema-safe)…")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=OFF;")

    cursor = conn.cursor()

    clear_tables(conn)
    print("🧹 Tables cleared")

    org_ids, oids = seed_organizations_and_oids(cursor)
    print("✅ organizations + primary OIDs")

    exec_ids = seed_pd_executions(cursor, oids)
    print("✅ pd_executions")

    seed_findings(cursor, exec_ids, oids)
    print("✅ findings")

    conn.commit()
    conn.close()

    print("🎉 Seed completed successfully")

if __name__ == "__main__":
    main()
