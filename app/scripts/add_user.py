import hashlib
import os
from datetime import datetime, timezone

from app.db.connection import get_connection

AUTH_PASSWORD_SALT = os.getenv("AUTH_PASSWORD_SALT", "dev_salt_123")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    combined = f"{AUTH_PASSWORD_SALT}:{password}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def reset_admin() -> None:
    conn = get_connection()
    password_hash = hash_password(ADMIN_PASSWORD)

    conn.execute("DELETE FROM users WHERE username = ?", (ADMIN_USERNAME,))
    conn.execute(
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
