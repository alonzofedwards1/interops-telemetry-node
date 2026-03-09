import logging

from app.db.connection import get_connection
from app.security.passwords import hash_password

logger = logging.getLogger(__name__)

username = "admin"
password = "Admin123!"


def seed_admin_user() -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        hashed = hash_password(password)

        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        user = cur.fetchone()

        if not user:
            cur.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (%s, %s, NOW())
                """,
                (username, hashed),
            )
            logger.info("AUTH_ADMIN_SEEDED", extra={"username": username})
        else:
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE username = %s
                """,
                (hashed, username),
            )
            logger.info("AUTH_ADMIN_PASSWORD_REFRESHED", extra={"username": username})

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed_admin_user()
    print("Admin credentials created:")
    print("username:", username)
    print("password:", password)
