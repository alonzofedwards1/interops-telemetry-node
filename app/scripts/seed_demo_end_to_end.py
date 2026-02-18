"""Seed demo data for end-to-end local testing against PostgreSQL."""

from datetime import datetime, timezone

from app.db.connection import get_connection


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    conn = get_connection()
    try:
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO pd_executions (request_id, started_at, completed_at, outcome, transaction_type)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (request_id) DO NOTHING
            """,
            ("demo-request-001", now, now, "success", "PD"),
        )
        conn.commit()
        print("✅ Demo seed complete")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
