import os
from dataclasses import dataclass
from typing import List

DEFAULT_PORT = 8081
DEFAULT_DB_PATH = "/data/telemetry.db"


@dataclass(frozen=True)
class Settings:
    """Application settings."""

    # Server
    port: int = int(os.environ.get("TELEMETRY_PORT", DEFAULT_PORT))

    # Database
    telemetry_db_path: str = os.environ.get(
        "TELEMETRY_DB_PATH",
        DEFAULT_DB_PATH,
    )

    # CORS
    allowed_origins: List[str] = None


def get_settings() -> Settings:
    origins_value = os.environ.get("CORS_ORIGINS", "*")
    origins = [o.strip() for o in origins_value.split(",") if o.strip()] or ["*"]

    return Settings(
        allowed_origins=origins,
    )
