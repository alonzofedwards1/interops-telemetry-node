import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

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

from app.config.settings import get_settings
from app.db.migrations import run_migrations
from app.scripts.seed_admin import seed_admin_user

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Settings
# ---------------------------------------------------------
settings = get_settings()

# ---------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------
app = FastAPI(
    title="InterOps Telemetry API",
    version="0.1.0",
)

# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---------------------------------------------------------
# Routers
# ---------------------------------------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(committee_queue_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(transport_router)
app.include_router(messages_router)
app.include_router(pd_executions_router, prefix="/api")
app.include_router(findings_router, prefix="/api")
app.include_router(oids_router, prefix="/api")
app.include_router(integration_health_router, prefix="/api")

# ---------------------------------------------------------
# Startup
# ---------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    logger.info("Running DB migrations...")
    run_migrations()
    logger.info("Ensuring default admin account...")
    seed_admin_user()

# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "database_url": settings.database_url,
        "port": settings.port,
        "environment": settings.environment,
        "allowed_origins": settings.allowed_origins,
    }


@app.api_route("/test", methods=["GET", "POST"])
async def test_endpoint(request: Request):
    if request.method == "GET":
        return {"message": "test endpoint working"}

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        raise HTTPException(status_code=400, detail="Content-Type must be application/json")

    body = await request.body()
    if not body.strip():
        raise HTTPException(status_code=400, detail="Request body cannot be empty")

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    return {"received": payload}

# ---------------------------------------------------------
# Local Dev Entry
# ---------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
    )
