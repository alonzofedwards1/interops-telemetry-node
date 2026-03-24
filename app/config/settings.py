import os
from dataclasses import dataclass
from typing import List

DEFAULT_PORT = 8081
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
    # CORS Origins
    origins_value = os.environ.get("CORS_ORIGINS")

    if origins_value:
        origins = [o.strip() for o in origins_value.split(",") if o.strip()]
    else:
        origins = list(DEFAULT_ALLOWED_ORIGINS)

    # Only force localhost in dev
    if os.environ.get("ENVIRONMENT", DEFAULT_ENVIRONMENT) == "dev":
        if "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")

    # REQUIRED VARIABLES (fail fast)
    database_url = os.environ["DATABASE_URL"]
    auth_password_salt = os.environ["AUTH_PASSWORD_SALT"]

    # OPTIONAL VARIABLES
    auth_cookie_secure = os.environ.get("AUTH_COOKIE_SECURE", "false").lower() == "true"

    return Settings(
        port=int(os.environ.get("TELEMETRY_PORT", DEFAULT_PORT)),
        database_url=database_url,
        environment=os.environ.get("ENVIRONMENT", DEFAULT_ENVIRONMENT),
        allowed_origins=origins,

        auth_cookie_name=os.environ.get("AUTH_COOKIE_NAME", "interoplens_session_id"),
        auth_cookie_secure=auth_cookie_secure,
        auth_session_ttl_seconds=int(
            os.environ.get("AUTH_SESSION_TTL_SECONDS", "43200")
        ),
        auth_password_salt=auth_password_salt,
    )