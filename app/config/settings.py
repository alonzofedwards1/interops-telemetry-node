import os
from dataclasses import dataclass
from typing import List

DEFAULT_PORT = 8081
DEFAULT_DATABASE_URL = (
    "postgresql://interoplens:devpassword@localhost:5432/interoplens"
)
DEFAULT_ENVIRONMENT = "dev"
DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3000"]


@dataclass(frozen=True)
class Settings:
    port: int
    database_url: str
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

    if "http://localhost:3000" not in origins:
        origins.append("http://localhost:3000")

    return Settings(
        port=int(os.environ.get("TELEMETRY_PORT", DEFAULT_PORT)),
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        environment=os.environ.get("ENVIRONMENT", DEFAULT_ENVIRONMENT),
        allowed_origins=origins,
        auth_cookie_name=os.environ.get("AUTH_COOKIE_NAME", "telemetry_auth"),
        auth_cookie_secure=False,
        auth_session_ttl_seconds=int(os.environ.get("AUTH_SESSION_TTL_SECONDS", "43200")),
        auth_password_salt=os.environ.get("AUTH_PASSWORD_SALT", "dev_salt_123"),
    )
