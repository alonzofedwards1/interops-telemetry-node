import os
import logging
from app.db.connection import get_connection
from app.auth.security import hash_password

logger = logging.getLogger(__name__)


def ensure_admin_user():
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD")

    if not password or len(password) < 12:
        raise ValueError("ADMIN_PASSWORD must be set and at least 12 characters")

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            logger.info("Checking for admin user...")

            cursor.execute(
                "SELECT id FROM users WHERE username = %s",
                (username,),
            )
            existing = cursor.fetchone()

            if existing:
                logger.info("Admin user already exists. Skipping creation.")
                return

            logger.info("Admin user not found. Creating admin user...")

            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    username,
                    f"{username}@interoplens.local",
                    hash_password(password),
                    "admin",
                ),
            )

            conn.commit()

            logger.info("Admin user created successfully.")

    finally:
        conn.close()