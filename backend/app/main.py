from fastapi import FastAPI

from app.api import routes_alerts, routes_categories, routes_current
from app.api.routes_health import router as health_router
from app.api.routes_metadata import router as metadata_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Rapid SCADA Telemetry Dashboard Backend",
    description="Read-only local backend for Rapid SCADA telemetry metadata and analytics.",
    version="0.1.0",
)

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(metadata_router)
app.include_router(routes_current.router)
app.include_router(routes_categories.router)
app.include_router(routes_alerts.router)


@app.get("/")
def root():
    """Return a simple root message."""
    return {
        "message": "Rapid SCADA Telemetry Dashboard Backend",
        "docs": "/docs",
        "health": "/api/health",
        "metadata_channels": "/api/metadata/channels",
        "categories_summary": "/api/categories/summary",
        "alerts": "/api/alerts",
        "overview": "/api/overview",
    }