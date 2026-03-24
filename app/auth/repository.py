from datetime import datetime

from app.db.connection import get_connection


def get_user_by_username(username: str):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, username, email, role, password_hash, totp_secret
            FROM users
            WHERE username = %s
            """,
            (username,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, username, email, role, totp_secret
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


def insert_session(
    user_id: int,
    token_hash: str,
    created_at: datetime,
    last_activity_at: datetime,
    expires_at: datetime,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO telemetry_sessions (
                user_id,
                token_hash,
                created_at,
                last_activity_at,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, token_hash, created_at, last_activity_at, expires_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_session_by_token_hash(token_hash: str):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_id, created_at, last_activity_at, expires_at
            FROM telemetry_sessions
            WHERE token_hash = %s
            """,
            (token_hash,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_session_activity(token_hash: str, last_activity_at: datetime) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE telemetry_sessions
            SET last_activity_at = %s
            WHERE token_hash = %s
            """,
            (last_activity_at, token_hash),
        )
        conn.commit()
    finally:
        conn.close()


def delete_session_by_token_hash(token_hash: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM telemetry_sessions WHERE token_hash = %s",
            (token_hash,),
        )
        conn.commit()
    finally:
        conn.close()
