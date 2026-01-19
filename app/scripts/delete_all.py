import sqlite3
from pathlib import Path

DB_PATH = Path(
    r"C:\Users\alonz\Documents\interops-telemetry-api\app\db\telemetry.db"
)

def wipe_all_tables():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    print(f"🧹 Wiping all tables in {DB_PATH}")

    # Disable FK enforcement during wipe
    cursor.execute("PRAGMA foreign_keys = OFF;")

    # Get all user tables (exclude sqlite internal tables)
    tables = cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%';
    """).fetchall()

    for (table_name,) in tables:
        print(f"  • Clearing {table_name}")
        cursor.execute(f"DELETE FROM {table_name};")

    conn.commit()

    # Optional: reset autoincrement counters (if any)
    cursor.execute("DELETE FROM sqlite_sequence;")
    conn.commit()

    conn.close()

    print("✅ All tables wiped successfully")

if __name__ == "__main__":
    wipe_all_tables()
