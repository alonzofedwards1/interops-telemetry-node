"""Seed PostgreSQL with representative InterOps telemetry data.

Usage:
    python -m app.scripts.seed_postgres
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from app.config.settings import get_settings
from app.db.connection import get_connection


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_password(password: str) -> str:
    settings = get_settings()
    payload = f"{settings.auth_password_salt}:{password}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    now = _utc_now()
    conn = get_connection()

    try:
        # telemetry_events + pd_executions
        for i in range(15):
            request_id = f"req-seed-{uuid.uuid4().hex[:10]}"
            event_id = f"evt-seed-{uuid.uuid4().hex[:10]}"
            ts = (datetime.now(timezone.utc) - timedelta(minutes=15 - i)).isoformat()
            status = "SUCCESS" if i % 4 else "ERROR"
            duration = 150 + (i * 25)

            conn.execute(
                """
                INSERT INTO telemetry_events (
                    event_id,
                    event_type,
                    event_layer,
                    timestamp_utc,
                    source_channel_id,
                    source_environment,
                    status,
                    duration_ms,
                    correlation_request_id,
                    cert_status,
                    cert_thumbprint,
                    raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb)
                ON CONFLICT (event_id) DO NOTHING
                """,
                (
                    event_id,
                    "pd.request.completed",
                    "transport",
                    ts,
                    "mirth-pd-01",
                    "dev",
                    status,
                    duration,
                    request_id,
                    "VALID",
                    "seed-thumbprint",
                    '{"seed": true}',
                ),
            )

            conn.execute(
                """
                INSERT INTO pd_executions (
                    request_id,
                    started_at,
                    completed_at,
                    duration_ms,
                    outcome,
                    transaction_type,
                    source_channel_id,
                    source_environment,
                    source_oid,
                    target_oid,
                    cert_status,
                    cert_thumbprint,
                    failure_stage,
                    root_cause,
                    http_status,
                    retry_count,
                    first_event_id,
                    last_event_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (request_id) DO NOTHING
                """,
                (
                    request_id,
                    ts,
                    ts,
                    duration,
                    "SUCCESS" if status == "SUCCESS" else "ERROR",
                    "PD",
                    "mirth-pd-01",
                    "dev",
                    "1.2.3.4.5.6",
                    "9.8.7.6.5.4",
                    "VALID",
                    "seed-thumbprint",
                    None,
                    "CERT_EXPIRED" if status != "SUCCESS" else None,
                    500 if status != "SUCCESS" else 200,
                    0,
                    event_id,
                    event_id,
                ),
            )

        # oid_directory
        conn.execute(
            """
            INSERT INTO oid_directory (
                oid,
                organization_name,
                status,
                confidence_score,
                first_seen_at,
                last_seen_at,
                reviewed_by,
                reviewed_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (oid) DO NOTHING
            """,
            (
                "1.2.3.4.5.6",
                "Seed Health Org",
                "ACTIVE",
                0.95,
                now,
                now,
                "seed-script",
                now,
                now,
                now,
            ),
        )

        # findings
        conn.execute(
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
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                "finding-seed-latency",
                "req-seed-sample",
                "PD",
                "warning",
                "Latency",
                "Seeded latency warning",
                "Synthetic finding inserted for dashboard validation.",
                "Review target channel latency trend.",
                "open",
                now,
                now,
                now,
            ),
        )

        # users
        conn.execute(
            """
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT (username) DO NOTHING
            """,
            ("admin", _hash_password("admin123"), now),
        )

        # transport_events
        for i in range(5):
            conn.execute(
                """
                INSERT INTO transport_events (
                    transaction_id,
                    channel,
                    request_method,
                    request_url,
                    request_headers,
                    response_status,
                    response_duration_ms,
                    source_ip,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?::jsonb, ?, ?, ?, ?)
                ON CONFLICT (transaction_id) DO NOTHING
                """,
                (
                    f"tx-seed-{i}",
                    "mirth-pd-01",
                    "POST",
                    "/pd/query",
                    '{"content-type":"application/json"}',
                    200 if i < 4 else 500,
                    120 + (i * 180),
                    "10.0.0.10",
                    now,
                ),
            )

        conn.commit()
        print("✅ PostgreSQL seed complete")
        print("   - telemetry_events: +15")
        print("   - pd_executions: +15")
        print("   - oid_directory: +1")
        print("   - findings: +1")
        print("   - users: admin/admin123 (created if missing)")
        print("   - transport_events: +5")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
