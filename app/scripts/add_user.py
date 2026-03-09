from datetime import datetime, timezone

from app.db.connection import get_connection
from app.security.passwords import hash_password

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin123!"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    print("password: Admin123!")


if __name__ == "__main__":
    reset_admin()
