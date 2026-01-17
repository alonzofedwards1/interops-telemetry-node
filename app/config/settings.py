import os
from dataclasses import dataclass
from typing import List
from pathlib import Path

# Project root
BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_PORT = 8081

# ✅ NEW: app/db/telemetry.db
DEFAULT_DB_PATH = str(BASE_DIR / "app" / "db" / "telemetry.db")

DEFAULT_ENVIRONMENT = "dev"


@dataclass(frozen=True)
class Settings:
    # Server
    port: int = int(os.environ.get("TELEMETRY_PORT", DEFAULT_PORT))

    # Database
    telemetry_db_path: str = os.environ.get(
        "TELEMETRY_DB_PATH",
        DEFAULT_DB_PATH,
    )

    # Environment
    environment: str = os.environ.get("ENVIRONMENT", DEFAULT_ENVIRONMENT)

    # CORS
    allowed_origins: List[str] | None = None

    # Auth
    auth_cookie_name: str = os.environ.get("AUTH_COOKIE_NAME", "telemetry_auth")
    auth_cookie_secure: bool = os.environ.get("AUTH_COOKIE_SECURE", "false").lower() == "true"
    auth_session_ttl_seconds: int = int(os.environ.get("AUTH_SESSION_TTL_SECONDS", "43200"))
    auth_password_salt: str = os.environ.get("AUTH_PASSWORD_SALT", "")


def get_settings() -> Settings:
    origins_value = os.environ.get("CORS_ORIGINS", "*")
    origins = [o.strip() for o in origins_value.split(",") if o.strip()] or ["*"]

    return Settings(
        allowed_origins=origins,
    )
