from app.db.connection import get_connection
from app.auth.security import hash_password

username = "admin"
password = "Admin123!"


conn = get_connection()
conn.execute(
    """
    INSERT INTO users (username, password_hash)
    VALUES (%s, %s)
    ON CONFLICT (username)
    DO UPDATE SET password_hash = EXCLUDED.password_hash
    """,
    (username, hash_password(password)),
)
conn.commit()
conn.close()

print("admin user ready")
