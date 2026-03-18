import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
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

from app.config.settings import get_settings
from app.db.migrations import run_migrations

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Settings
settings = get_settings()


# FastAPI App
app = FastAPI(
    title="InterOps Telemetry API",
    version="0.1.0",
)


@app.middleware("http")
async def debug_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.exception(
            "UNHANDLED_EXCEPTION",
            extra={
                "path": request.url.path,
                "method": request.method,
            },
        )
        raise e

# CORS
# Ensure React dev server works even if settings are empty
# CORS
allowed_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS enabled for: {allowed_origins}")
logger.info(f"CORS enabled for: {allowed_origins}")

# Routers
app.include_router(auth_router, prefix="/api")

app.include_router(committee_queue_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(pd_executions_router, prefix="/api")
app.include_router(findings_router, prefix="/api")
app.include_router(oids_router, prefix="/api")
app.include_router(integration_health_router, prefix="/api")

# Routers that define their own prefix internally
app.include_router(messages_router)
app.include_router(transport_router)

# Startup
@app.on_event("startup")
async def startup() -> None:
    logger.info("Running DB migrations...")
    run_migrations()

# Health Check

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "database_url": settings.database_url,
        "port": settings.port,
        "environment": settings.environment,
        "allowed_origins": allowed_origins,
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
    )
