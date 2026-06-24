from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")

def health_check():
    """Return basic backend health information."""
    return {
        "status": "ok",
        "service": "rapid-scada-telemetry-dashboard-backend",
        "version": "0.1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }