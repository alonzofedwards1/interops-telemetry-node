import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv


load_dotenv()

# Ensure project root is on sys.path
ROOT_PATH = Path(__file__).resolve().parent.parent
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

# Routers
from app.api.auth import router as auth_router
from app.api.committee_queue import router as committee_queue_router
from app.api.findings import router as findings_router
from app.api.integration_health import router as integration_health_router
from app.api.messages import router as messages_router
from app.api.oids import router as oids_router
from app.api.pd_executions import router as pd_executions_router
from app.api.telemetry import router as telemetry_router
from app.api.transport_routes import router as transport_router

# Config / DB
from app.config.settings import get_settings
from app.db.migrations import run_migrations

# ✅ NEW: Admin bootstrap
from app.services.user_service import ensure_admin_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Settings
settings = get_settings()

app = FastAPI(
    title="InterOps Telemetry API",
    version="0.1.0",
)


allowed_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS enabled for: {allowed_origins}")


app.include_router(auth_router, prefix="/api")
app.include_router(committee_queue_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(pd_executions_router, prefix="/api")
app.include_router(findings_router, prefix="/api")
app.include_router(oids_router, prefix="/api")
app.include_router(integration_health_router, prefix="/api")

# Routers with internal prefixes
app.include_router(messages_router)
app.include_router(transport_router)


@app.on_event("startup")
async def startup() -> None:
    logger.info("Starting InterOps API...")

    # Run migrations first
    logger.info("Running DB migrations...")
    run_migrations()

    # ✅ Ensure admin user exists
    logger.info("Ensuring admin user exists...")
    ensure_admin_user()

    logger.info("Startup complete.")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "environment": settings.environment,
        "port": settings.port,
        "allowed_origins": allowed_origins,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
    )