"""
Seed script for telemetry_events table.

Purpose:
- Insert synthetic Patient Discovery telemetry events
- Used for local development, UI testing, and dashboard validation

Usage:
    python app/scripts/seed_telemetry_events.py
"""

import sqlite3
import random
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path

# -----------------------------
# CONFIGURATION
# -----------------------------

# Resolve to project root telemetry.db
# app/scripts -> app -> project root
DB_PATH = Path(__file__).resolve().parents[2] / "telemetry.db"

TOTAL_RECORDS = 100

EVENT_TYPES = [
    "pd.request.completed",
]

OUTCOMES = [
    "success",
    "error",
]

ENVIRONMENTS = ["DEV", "TEST", "PROD"]

CHANNELS = [
    "mirth-pd-01",
    "mirth-pd-02",
    "mirth-pd-03",
]

# -----------------------------
# DATABASE CONNECTION
# -----------------------------

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print(f"Using database: {DB_PATH}")

# -----------------------------
# DATA GENERATION
# -----------------------------

# Base time = 1 hour ago
base_time = datetime.now(UTC) - timedelta(hours=1)

rows = []

for i in range(TOTAL_RECORDS):
    request_id = f"req-test-{uuid.uuid4()}"
    event_type = EVENT_TYPES[0]

    outcome = random.choices(
        OUTCOMES,
        weights=[0.85, 0.15],  # 85% success, 15% error
        k=1
    )[0]

    duration_ms = random.randint(120, 2200)
    timestamp = base_time + timedelta(seconds=i * 5)

    rows.append((
        request_id,
        event_type,
        timestamp.isoformat(),
        outcome,
        duration_ms,
        random.choice(ENVIRONMENTS),
        random.choice(CHANNELS),
    ))

# -----------------------------
# INSERT RECORDS
# -----------------------------

cursor.executemany(
    """
    INSERT INTO telemetry_events (
        request_id,
        event_type,
        timestamp,
        outcome,
        duration_ms,
        source_environment,
        source_channel
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    rows
)

conn.commit()
conn.close()

print(f"✅ Inserted {len(rows)} telemetry_events records")
