import os
from dataclasses import dataclass
from typing import List
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_PORT = 8081
DEFAULT_DB_PATH = str(BASE_DIR / "app" / "db" / "telemetry.db")
DEFAULT_ENVIRONMENT = "dev"
DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3000"]


@dataclass(frozen=True)
class Settings:
    port: int
    telemetry_db_path: str
    environment: str
    allowed_origins: List[str]

    auth_cookie_name: str
    auth_cookie_secure: bool
    auth_session_ttl_seconds: int
    auth_password_salt: str


def get_settings() -> Settings:
    origins_value = os.environ.get("CORS_ORIGINS")
    if origins_value:
        origins = [o.strip() for o in origins_value.split(",") if o.strip()]
    else:
        origins = DEFAULT_ALLOWED_ORIGINS

    return Settings(
        port=int(os.environ.get("TELEMETRY_PORT", DEFAULT_PORT)),
        telemetry_db_path=os.environ.get("TELEMETRY_DB_PATH", DEFAULT_DB_PATH),
        environment=os.environ.get("ENVIRONMENT", DEFAULT_ENVIRONMENT),
        allowed_origins=origins,

        auth_cookie_name=os.environ.get("AUTH_COOKIE_NAME", "telemetry_auth"),
        auth_cookie_secure=os.environ.get("AUTH_COOKIE_SECURE", "false").lower() == "true",
        auth_session_ttl_seconds=int(os.environ.get("AUTH_SESSION_TTL_SECONDS", "43200")),
        auth_password_salt=os.environ.get("AUTH_PASSWORD_SALT", "dev_salt_123"),
    )
