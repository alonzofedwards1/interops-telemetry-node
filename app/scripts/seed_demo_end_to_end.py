import sqlite3
import random
from datetime import datetime, timedelta, timezone

# ============================================================
# CONFIG
# ============================================================

DB_PATH = r"C:\Users\alonz\Documents\interops-telemetry-api\app\db\telemetry.db"

TOTAL_TRANSACTIONS = 250
CHANNEL = "pd-gateway"
ENVIRONMENT = "Production"

AUTH_FAILURE_RATE = 0.25
LATENCY_WARNING_RATE = 0.30
FAILURE_RATE = 0.10

# ============================================================
# RAW HCID / OID POOL (SIMULATED REAL-WORLD PARTICIPANTS)
# ============================================================

HCIDS = [
    ("2.16.840.1.113883.3.247", "Epic Systems Corporation"),
    ("2.16.840.1.113883.3.600.1.1570", "CRISP HIE"),
    ("2.16.840.1.113883.3.962", "eHealth Exchange"),
    ("2.16.840.1.113883.3.18.7", "CommonWell Health Alliance"),
    ("2.16.840.1.113883.3.13.6.7", "Carequality"),
]

# ============================================================
# HELPERS
# ============================================================

def now(offset_seconds: int = 0) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    ).isoformat()

def txn_id(i: int) -> str:
    return f"pd-2026-01-11-{i:04d}"

def event_id(i: int, j: int) -> str:
    return f"evt-{i:04d}-{j}"

# ============================================================
# CONNECT
# ============================================================

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ============================================================
# RESET DATABASE (DEMO SAFE)
# ============================================================

print("🧹 RESETTING DATABASE...")

cur.execute("DELETE FROM findings;")
cur.execute("DELETE FROM pd_executions;")
cur.execute("DELETE FROM telemetry_events;")
cur.execute("DELETE FROM organization_oids;")
cur.execute("DELETE FROM organizations;")
cur.execute("DELETE FROM oid_directory;")

conn.commit()

# ============================================================
# OID REGISTRATION (AUTOMATED, NON-BLOCKING)
# ============================================================

def register_observed_oid(oid: str, org_name: str | None):
    ts = now()

    cur.execute(
        """
        INSERT INTO oid_directory (
            oid,
            organization_name,
            status,
            first_seen_at,
            last_seen_at,
            created_at,
            updated_at
        )
        VALUES (?, ?, 'provisional', ?, ?, ?, ?)
        ON CONFLICT(oid) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            updated_at = excluded.updated_at
        """,
        (oid, org_name, ts, ts, ts, ts)
    )

# ============================================================
# LOAD GENERATION
# ============================================================

print(f"🚀 Generating {TOTAL_TRANSACTIONS} PD transactions with identity...")

for i in range(1, TOTAL_TRANSACTIONS + 1):

    request_id = txn_id(i)
    base_offset = i * 3

    has_auth_issue = random.random() < AUTH_FAILURE_RATE
    has_latency = random.random() < LATENCY_WARNING_RATE
    is_failure = random.random() < FAILURE_RATE

    duration_ms = (
        random.randint(15000, 28000)
        if has_latency
        else random.randint(800, 4500)
    )

    outcome = "failure" if is_failure else "success"

    # --------------------------------------------------------
    # PICK REALISTIC SENDER / RECEIVER HCIDS
    # --------------------------------------------------------

    (source_oid, source_name) = random.choice(HCIDS)
    (target_oid, target_name) = random.choice(
        [h for h in HCIDS if h[0] != source_oid]
    )

    # Auto-register identity evidence
    register_observed_oid(source_oid, source_name)
    register_observed_oid(target_oid, target_name)

    # --------------------------------------------------------
    # TELEMETRY EVENTS (RAW EVIDENCE)
    # --------------------------------------------------------

    events = []

    events.append({
        "event_id": event_id(i, 1),
        "type": "PD.RequestSent",
        "ts": now(base_offset),
        "status": "info",
        "duration": None,
        "payload": "Patient Discovery request sent"
    })

    if has_auth_issue:
        events.append({
            "event_id": event_id(i, 2),
            "type": "PD.AuthFailed",
            "ts": now(base_offset + 2),
            "status": "error",
            "duration": None,
            "payload": "HTTP 401 Unauthorized"
        })
        events.append({
            "event_id": event_id(i, 3),
            "type": "PD.AuthFailed",
            "ts": now(base_offset + 3),
            "status": "error",
            "duration": None,
            "payload": "HTTP 401 Unauthorized"
        })

    events.append({
        "event_id": event_id(i, 9),
        "type": "PD.RequestCompleted",
        "ts": now(base_offset + 6),
        "status": outcome,
        "duration": duration_ms,
        "payload": "Patient Discovery completed"
    })

    for e in events:
        cur.execute(
            """
            INSERT INTO telemetry_events (
                event_id,
                event_type,
                timestamp_utc,
                source_channel_id,
                source_environment,
                status,
                duration_ms,
                correlation_request_id,
                raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["event_id"],
                e["type"],
                e["ts"],
                CHANNEL,
                ENVIRONMENT,
                e["status"],
                e["duration"],
                request_id,
                e["payload"],
            ),
        )

    # --------------------------------------------------------
    # PD EXECUTION (IDENTITY-AWARE)
    # --------------------------------------------------------

    cur.execute(
        """
        INSERT INTO pd_executions (
            request_id,
            started_at,
            completed_at,
            duration_ms,
            outcome,
            source_channel_id,
            source_environment,
            first_event_id,
            last_event_id,
            source_oid,
            target_oid
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_id,
            events[0]["ts"],
            events[-1]["ts"],
            duration_ms,
            outcome,
            CHANNEL,
            ENVIRONMENT,
            events[0]["event_id"],
            events[-1]["event_id"],
            source_oid,
            target_oid,
        ),
    )

    # --------------------------------------------------------
    # FINDINGS (DERIVED CONCLUSIONS)
    # --------------------------------------------------------

    if has_auth_issue:
        cur.execute(
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
                first_seen_at,
                last_seen_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"finding-auth-{i:04d}",
                request_id,
                "PD",
                "critical",
                "connectivity",
                "Authentication failures detected during Patient Discovery",
                "Repeated HTTP 401 responses returned by the partner exchange",
                "Verify authentication credentials configured for the exchange",
                "open",
                events[1]["ts"],
                events[2]["ts"],
                now(),
            ),
        )

    if has_latency:
        cur.execute(
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
                first_seen_at,
                last_seen_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"finding-perf-{i:04d}",
                request_id,
                "PD",
                "warning",
                "performance",
                "Patient Discovery latency exceeds recommended guidance",
                f"Total response time was {duration_ms} ms (recommended < 5000 ms)",
                "Investigate downstream system performance and network latency",
                "open",
                events[0]["ts"],
                events[-1]["ts"],
                now(),
            ),
        )

    if i % 50 == 0:
        conn.commit()
        print(f"✔ Seeded {i} transactions")

# ============================================================
# DONE
# ============================================================

conn.commit()
conn.close()

print("\n🎉 LOAD TEST DATA GENERATED SUCCESSFULLY")
print("You now have:")
print("• Identity-aware PD executions")
print("• Provisional OIDs in the directory")
print("• Realistic telemetry and findings")
print("• A demo that mirrors real PD traffic")
