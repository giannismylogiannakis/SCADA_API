import xml.etree.ElementTree as ET
from typing import Any

from fastapi import APIRouter, HTTPException

from app.analytics.categories import build_category_summary
from app.metadata.xml_loader import load_channels_metadata


router = APIRouter(prefix="/api/categories", tags=["categories"])


def _to_plain_dict(value: Any) -> dict[str, Any]:
    """Convert metadata model/plain object to dictionary."""
    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    if hasattr(value, "__dict__"):
        return dict(value.__dict__)

    return {}


def _is_active(channel: dict[str, Any]) -> bool:
    """Return True when a metadata channel is active."""
    active = channel.get("active")

    if isinstance(active, bool):
        return active

    if isinstance(active, int):
        return active == 1

    if isinstance(active, str):
        return active.strip().lower() in {"true", "1", "yes", "y"}

    return False


@router.get("/summary")
def get_categories_summary(active_only: bool = True) -> dict[str, Any]:
    """Return channel counts per inferred/manual category."""
    try:
        channels = [_to_plain_dict(channel) for channel in load_channels_metadata()]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ET.ParseError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid XML file: {exc}") from exc

    if active_only:
        channels = [channel for channel in channels if _is_active(channel)]

    summary = build_category_summary(channels)

    return {
        "ok": True,
        "active_only": active_only,
        **summary,
    }