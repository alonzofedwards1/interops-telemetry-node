# app/integration_health/store.py

def get_integration_health(conn):

    exec_row = conn.execute("""
        SELECT
            COUNT(*) AS "totalExecutions",
            SUM(CASE WHEN LOWER(outcome) = 'success' THEN 1 ELSE 0 END) AS "successExecutions",
            COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN source_oid END) AS "affectedPartners"
        FROM pd_executions
    """).fetchone()

    total = exec_row["totalExecutions"] or 0
    success = exec_row["successExecutions"] or 0

    cert_row = conn.execute("""
        SELECT
          COUNT(*) FILTER (
            WHERE not_after IS NULL OR not_after < NOW()
          ) AS expired,

          COUNT(*) FILTER (
            WHERE not_after >= NOW()
              AND not_after <= NOW() + INTERVAL '30 days'
          ) AS expiring_soon,

          COUNT(*) FILTER (
            WHERE not_after > NOW() + INTERVAL '30 days'
          ) AS valid

        FROM public.certificates
    """).fetchone()

    expired = cert_row["expired"] or 0
    expiring_soon = cert_row["expiring_soon"] or 0
    valid = cert_row["valid"] or 0

    print(
        f"[CERT HEALTH] expired={expired}, "
        f"expiringSoon={expiring_soon}, "
        f"valid={valid}"
    )

    return {
        "totalExecutions": total,
        "successRate": round((success / total) * 100, 2) if total else 0,
        "certificateHealth": {
            "expired": expired,
            "expiringSoon": expiring_soon,
            "valid": valid,
        },
        "affectedPartners": exec_row["affectedPartners"] or 0,
    }