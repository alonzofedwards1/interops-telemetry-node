def get_integration_health(conn):
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS "totalExecutions",
            SUM(CASE WHEN LOWER(outcome) = 'success' THEN 1 ELSE 0 END) AS "successExecutions",
            COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN cert_thumbprint END) AS "expiredCerts",
            COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN source_oid END) AS "affectedPartners"
        FROM pd_executions
        """
    ).fetchone()

    total = row["totalExecutions"] or 0
    success = row["successExecutions"] or 0

    return {
        "totalExecutions": total,
        "successRate": round((success / total) * 100, 2) if total else 0,
        "certificateHealth": {
            "expired": row["expiredCerts"] or 0,
            "expiringSoon": 0,
            "valid": None,
        },
        "affectedPartners": row["affectedPartners"] or 0,
    }
