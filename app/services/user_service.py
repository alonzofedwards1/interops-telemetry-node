from app.db.connection import get_connection
from app.auth import repository
from app.auth.security import verify_password, hash_password
import secrets
import hashlib
from datetime import datetime, timedelta
import pyotp


# ---------------------------------------------------------
# Admin Seeder
# ---------------------------------------------------------
def ensure_admin_user():
    """
    Ensures a default admin user exists.
    Runs on app startup.
    """

    admin_username = "admin"
    admin_password = "admin123"

    existing = repository.get_user_by_username(admin_username)

    if existing:
        return

    repository.create_user(
        username=admin_username,
        password_hash=hash_password(admin_password),
        is_admin=True,
    )


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------
# Authentication (Step 1)
# ---------------------------------------------------------
from app.auth.security import verify_password


def verify_credentials(username: str, password: str):
    user = repository.get_user_by_username(username)

    print("----- LOGIN DEBUG START -----")
    print("USERNAME:", username)

    if not user:
        print("🚨 USER NOT FOUND IN DB")
        print("----- LOGIN DEBUG END -----")
        raise Exception("Invalid credentials")

    print("DB HASH:", user["password_hash"])

    verify_result = verify_password(password, user["password_hash"])
    print("VERIFY RESULT:", verify_result)

    print("----- LOGIN DEBUG END -----")

    if not verify_result:
        raise Exception("Invalid credentials")

    return user


# ---------------------------------------------------------
# Session Creation
# ---------------------------------------------------------
def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)

    expires_at = datetime.utcnow() + timedelta(hours=8)

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO telemetry_sessions (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, token_hash, expires_at),
        )
        conn.commit()
    finally:
        conn.close()

    return token


# ---------------------------------------------------------
# Session Validation
# ---------------------------------------------------------
def get_session_user(token: str):
    token_hash = hash_token(token)

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_id
            FROM telemetry_sessions
            WHERE token_hash = %s
              AND expires_at > NOW()
            """,
            (token_hash,),
        ).fetchone()

        if not row:
            return None

        conn.execute(
            """
            UPDATE telemetry_sessions
            SET last_activity_at = NOW()
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        conn.commit()

        return row["user_id"]

    finally:
        conn.close()


# ---------------------------------------------------------
# MFA (TOTP)
# ---------------------------------------------------------
def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code)


def complete_mfa(user_id: int, code: str) -> str:
    user = repository.get_user_by_id(user_id)

    if not user or not user.get("totp_secret"):
        raise Exception("MFA not configured")

    if not verify_totp_code(user["totp_secret"], code):
        raise Exception("Invalid MFA code")

    return create_session(user_id)


# ---------------------------------------------------------
# Login (Full Flow Entry Point)
# ---------------------------------------------------------
def login(username: str, password: str):
    user = verify_credentials(username, password)

    # MFA gate
    if user.get("mfa_enabled"):
        return {
            "mfa_required": True,
            "user_id": user["id"],
        }

    # No MFA → create session
    token = create_session(user["id"])
    return {"token": token}


# ---------------------------------------------------------
# Logout
# ---------------------------------------------------------
def logout(token: str):
    token_hash = hash_token(token)

    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM telemetry_sessions WHERE token_hash = %s",
            (token_hash,),
        )
        conn.commit()
    finally:
        conn.close()