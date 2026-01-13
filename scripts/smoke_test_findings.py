import logging
from datetime import datetime, timezone

from app.db.connection import get_connection
from app.findings.repository import add_or_update_finding, get_findings_counts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='findings'"
        ).fetchone()
        if not row:
            raise RuntimeError("findings table not found")
        logger.info("findings table present")
    finally:
        conn.close()

    before = get_findings_counts()
    logger.info("counts before: %s", before)

    add_or_update_finding(
        id=f"finding-smoke-{_utc_now()}",
        execution_id="req-local-001",
        execution_type="PD",
        severity="warning",
        category="Smoke",
        summary="Smoke test finding",
        technical_detail="Inserted by smoke test",
        recommended_action=None,
        status="open",
    )

    after = get_findings_counts()
    logger.info("counts after: %s", after)


if __name__ == "__main__":
    main()
