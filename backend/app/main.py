from fastapi import FastAPI

from app.api import routes_current
from app.api.routes_health import router as health_router
from app.api.routes_metadata import router as metadata_router

app = FastAPI(
    title="Rapid SCADA Telemetry Dashboard Backend",
    description="Read-only local backend for Rapid SCADA telemetry metadata and analytics.",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(metadata_router)
app.include_router(routes_current.router)


@app.get("/")
def root():
    """Return a simple root message."""
    return {
        "message": "Rapid SCADA Telemetry Dashboard Backend",
        "docs": "/docs",
        "health": "/api/health",
        "metadata_channels": "/api/metadata/channels",
    }