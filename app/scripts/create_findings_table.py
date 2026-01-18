import logging
from pathlib import Path

from app.db.connection import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema_findings.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    logger.info("Applying findings schema from %s", schema_path)
    conn = get_connection()
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()

    print("✅ Findings table created/verified.")


if __name__ == "__main__":
    main()
