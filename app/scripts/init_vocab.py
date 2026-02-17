"""Initialize optional vocabulary seed data in PostgreSQL."""

from app.db.connection import get_connection


def main() -> None:
    conn = get_connection()
    try:
        # Placeholder for future vocab seed tables.
        conn.commit()
        print("✅ Vocabulary initialization completed (no-op)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
