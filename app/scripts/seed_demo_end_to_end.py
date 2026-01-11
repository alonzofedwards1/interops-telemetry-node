import sqlite3
import random
from datetime import datetime, timedelta, timezone

# ============================================================
# CONFIG
# ============================================================

DB_PATH = r"C:\Users\alonz\Documents\interops-telemetry-api\app\db\telemetry.db"

TOTAL_TRANSACTIONS = 250   # increase to 500 / 1000 if desired
CHANNEL = "pd-gateway"
ENVIRONMENT = "Production"

AUTH_FAILURE_RATE = 0.25     # 25% have auth issues
LATENCY_WARNING_RATE = 0.30  # 30% slow responses
FAILURE_RATE = 0.10          # 10% outright failures

# ============================================================
# Helpers
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
# Connect
# ============================================================

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ============================================================
# RESET DATABASE (CRITICAL FOR DEMOS)
# ============================================================

print("🧹 RESETTING DATABASE FOR LOAD TEST...")

cur.execute("DELETE FROM findings;")
cur.execute("DELETE FROM pd_executions;")
cur.execute("DELETE FROM telemetry_events;")
conn.commit()

# ============================================================
# LOAD GENERATION
# ============================================================

print(f"🚀 Generating {TOTAL_TRANSACTIONS} PD transactions...")

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
    # TELEMETRY EVENTS (EVIDENCE)
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
    # PD EXECUTION (TRANSACTION)
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
            last_event_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        ),
    )

    # --------------------------------------------------------
    # FINDINGS (INTERPRETED CONCLUSIONS)
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

    # --------------------------------------------------------
    # Batch commit (SQLite-friendly)
    # --------------------------------------------------------

    if i % 50 == 0:
        conn.commit()
        print(f"✔ Seeded {i} transactions")

# ============================================================
# Done
# ============================================================

conn.commit()
conn.close()

print("\n🎉 LOAD TEST DATA GENERATED SUCCESSFULLY")
print("You can now demo:")
print("• Hundreds of PD transactions")
print("• Mixed outcomes and findings")
print("• Realistic dashboards under load")
