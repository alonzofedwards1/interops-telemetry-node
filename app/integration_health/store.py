import sqlite3
from typing import Any, Dict

from app.db.connection import get_connection


def get_integration_health(conn: sqlite3.Connection | None = None) -> Dict[str, Any]:
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_executions,
                SUM(
                    CASE
                        WHEN LOWER(COALESCE(outcome, '')) = 'success' THEN 1
                        ELSE 0
                    END
                ) AS success_executions,
                COUNT(
                    DISTINCT CASE
                        WHEN root_cause = 'CERT_EXPIRED' THEN cert_thumbprint
                        ELSE NULL
                    END
                ) AS expired_certificates,
                COUNT(
                    DISTINCT CASE
                        WHEN root_cause = 'CERT_EXPIRED' THEN qhin_name
                        ELSE NULL
                    END
                ) AS affected_partners
            FROM pd_executions
            """
        ).fetchone()

        total_executions = int(row[0] or 0) if row else 0
        success_executions = int(row[1] or 0) if row else 0
        expired_certificates = int(row[2] or 0) if row else 0
        affected_partners = int(row[3] or 0) if row else 0

        success_rate = (
            (success_executions / total_executions) * 100
            if total_executions > 0
            else 0
        )

        return {
            "totalExecutions": total_executions,
            "successRate": success_rate,
            "certificateHealth": {
                "expired": expired_certificates,
                "expiringSoon": 0,
                "valid": None,
            },
            "affectedPartners": affected_partners,
        }
    finally:
        if close_conn:
            conn.close()
