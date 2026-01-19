import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import os

DB_PATH = Path(
    r"C:\Users\alonz\Documents\interops-telemetry-api\app\db\telemetry.db"
)

# MUST MATCH ENV
AUTH_PASSWORD_SALT = os.getenv("AUTH_PASSWORD_SALT", "dev_salt_123")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def now():
    return datetime.now(timezone.utc).isoformat()

def hash_password(password: str) -> str:
    combined = f"{AUTH_PASSWORD_SALT}:{password}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

def reset_admin():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    # Remove old admin (bad hash)
    cursor.execute("DELETE FROM users WHERE username = ?", (ADMIN_USERNAME,))

    password_hash = hash_password(ADMIN_PASSWORD)

    cursor.execute(
        """
        INSERT INTO users (username, password_hash, created_at)
        VALUES (?, ?, ?)
        """,
        (ADMIN_USERNAME, password_hash, now()),
    )

    conn.commit()
    conn.close()

    print("✅ Admin user reset")
    print("username: admin")
    print("password: admin123")
    print("salt used:", AUTH_PASSWORD_SALT)
    print("hash:", password_hash)

if __name__ == "__main__":
    reset_admin()
