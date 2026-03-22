from app.db.connection import get_connection


def get_user_by_username(username: str):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, username, email, role, password_hash
            FROM users
            WHERE username = %s
            """,
            (username,),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, username, email, role
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        ).fetchone()

        return dict(row) if row else None
    finally:
        conn.close()


def update_user_password(user_id: int, password_hash: str):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (password_hash, user_id),
        )
        conn.commit()
    finally:
        conn.close()