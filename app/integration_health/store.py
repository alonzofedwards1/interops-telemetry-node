import sqlite3

def get_integration_health(db: sqlite3.Connection):
    sql = """
        SELECT
            COUNT(*) AS total_executions,
            SUM(CASE WHEN LOWER(outcome) = 'success' THEN 1 ELSE 0 END) AS success_executions,
            COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN cert_thumbprint END) AS expired_certs,
            COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN qhin_name END) AS affected_partners
        FROM pd_executions
    """

    row = db.execute(sql).fetchone()

    total = row[0] or 0
    success = row[1] or 0

    return {
        "totalExecutions": total,
        "successRate": round((success / total) * 100, 2) if total else 0,
        "certificateHealth": {
            "expired": row[2] or 0,
            "expiringSoon": 0,
            "valid": None
        },
        "affectedPartners": row[3] or 0
    }
