from app.db.connection import get_connection


def wipe_all_tables() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    print("🧹 Wiping all public tables")

    cursor.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        """
    )
    tables = [row[0] for row in cursor.fetchall()]

    for table_name in tables:
        print(f"  • Clearing {table_name}")
        cursor.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE;')

    conn.commit()
    conn.close()
    print("✅ All tables wiped successfully")


if __name__ == "__main__":
    wipe_all_tables()
