from app.db.connection import get_connection


def get_user_by_username(username: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, password_hash FROM users WHERE username = %s",
            (username,),
        ).fetchone()
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