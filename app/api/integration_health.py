from fastapi import APIRouter, Depends
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "db" / "telemetry.db"

router = APIRouter(
    prefix="/health",
    tags=["Integration Health"]
)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

@router.get("/integrations")
def get_integration_health(db: sqlite3.Connection = Depends(get_db)):
    sql = """
        SELECT
            COUNT(*) AS totalExecutions,
            SUM(CASE WHEN LOWER(outcome) = 'success' THEN 1 ELSE 0 END) AS successExecutions,
            COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN cert_thumbprint END) AS expiredCerts,
            COUNT(DISTINCT CASE WHEN root_cause = 'CERT_EXPIRED' THEN qhin_name END) AS affectedPartners
        FROM pd_executions
    """

    row = db.execute(sql).fetchone()

    total = row["totalExecutions"] or 0
    success = row["successExecutions"] or 0

    return {
        "totalExecutions": total,
        "successRate": round((success / total) * 100, 2) if total else 0,
        "certificateHealth": {
            "expired": row["expiredCerts"] or 0,
            "expiringSoon": 0,
            "valid": None
        },
        "affectedPartners": row["affectedPartners"] or 0
    }
