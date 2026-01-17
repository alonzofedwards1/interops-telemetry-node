import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT_PATH = Path(__file__).resolve().parent.parent
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from app.api.auth import router as auth_router
from app.api.findings import router as findings_router
from app.api.oids import router as oids_router
from app.api.pd_executions import router as pd_executions_router
from app.api.telemetry import router as telemetry_router
from app.config.settings import get_settings
from app.db.migrations import run_migrations

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(title="InterOps Telemetry API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,   # MUST be explicit
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,                   # Cookies enabled
)

app.include_router(auth_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(pd_executions_router, prefix="/api")
app.include_router(findings_router, prefix="/api")
app.include_router(oids_router, prefix="/api")


@app.on_event("startup")
async def startup() -> None:
    run_migrations()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "db_path": settings.telemetry_db_path,
        "port": settings.port,
        "environment": settings.environment,
        "allowed_origins": settings.allowed_origins,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
    )
