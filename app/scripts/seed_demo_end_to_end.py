import sqlite3
import uuid
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

DB_PATH = Path.cwd() / "app" / "db" / "telemetry.db"

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
# CLEAR TABLES
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
        try:
            cur.execute(f"DELETE FROM {t}")
        except sqlite3.OperationalError:
            print(f"Skipping missing table: {t}")
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

        # ✔ FIXED STATUS HERE → ACTIVE
        cur.execute("""
            INSERT INTO oid_directory (
                oid, organization_name, organization_type,
                qhin_name, hie_name, status,
                confidence_score, first_seen_at, last_seen_at
            ) VALUES (?, ?, 'Hospital', 'CommonWell', 'Carequality',
                     'ACTIVE', ?, ?, ?)
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
# MAIN
# ============================================================

def main():
    print("🚀 Telemetry seed starting")
    print("DB Path:", DB_PATH)

    conn = sqlite3.connect(DB_PATH, timeout=60)
    tune_sqlite(conn)
    cur = conn.cursor()

    clear_tables(conn)
    print("🧹 Tables cleared")

    oids = seed_organizations(cur)
    conn.commit()
    print(f"🏥 {len(oids)} orgs seeded")

    conn.close()
    print("✅ Seed complete")

if __name__ == "__main__":
    main()
