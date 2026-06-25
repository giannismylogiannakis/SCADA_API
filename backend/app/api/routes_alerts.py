from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.analytics.rules_engine import build_overview, evaluate_channels
from app.api.routes_current import (
    batch_items,
    build_status_counts,
    expand_cnl_nums,
    get_channel_num,
    load_metadata_channels,
    merge_current_with_metadata,
    parse_current_data,
)
from app.core.config import settings
from app.scada.client import ScadaApiClient, ScadaApiError


router = APIRouter(prefix="/api", tags=["alerts"])


async def build_current_snapshot(
    cnl_nums: str | None = None,
) -> dict[str, Any]:
    """Read current values from SCADA and merge them with metadata."""
    fetched_at = datetime.now(timezone.utc).isoformat()

    all_active_metadata = load_metadata_channels(active_only=True)
    metadata_by_cnl_num = {
        get_channel_num(channel): channel
        for channel in all_active_metadata
        if get_channel_num(channel) is not None
    }

    if cnl_nums:
        requested_nums = expand_cnl_nums(cnl_nums)
        metadata_channels = [
            metadata_by_cnl_num[num]
            for num in requested_nums
            if num in metadata_by_cnl_num
        ]
        missing_metadata_nums = [
            num for num in requested_nums if num not in metadata_by_cnl_num
        ]
    else:
        metadata_channels = all_active_metadata
        requested_nums = [
            get_channel_num(channel)
            for channel in metadata_channels
            if get_channel_num(channel) is not None
        ]
        missing_metadata_nums = []

    requested_nums = sorted(set(int(num) for num in requested_nums if num is not None))

    if not requested_nums:
        return {
            "ok": True,
            "fetched_at": fetched_at,
            "requested_count": 0,
            "returned_count": 0,
            "batches_count": 0,
            "status_counts": {},
            "missing_metadata_cnl_nums": missing_metadata_nums,
            "items": [],
        }

    raw_batches: list[Any] = []
    current_by_cnl_num: dict[int, dict[str, Any]] = {}

    async with ScadaApiClient(
        base_url=settings.scada_base_url,
        username=settings.scada_username,
        password=settings.scada_password,
        timeout_seconds=settings.scada_request_timeout_seconds,
    ) as client:
        await client.login()

        for batch in batch_items(requested_nums):
            batch_query = ",".join(str(num) for num in batch)
            raw_response = await client.get_current_data(batch_query)
            raw_batches.append(raw_response)

            parsed_batch = parse_current_data(raw_response)
            current_by_cnl_num.update(parsed_batch)

        await client.logout()

    items = merge_current_with_metadata(
        metadata_channels=metadata_channels,
        current_by_cnl_num=current_by_cnl_num,
        include_raw=False,
    )

    for item in items:
        item["fetched_at"] = fetched_at

    return {
        "ok": True,
        "fetched_at": fetched_at,
        "requested_count": len(requested_nums),
        "returned_count": len(current_by_cnl_num),
        "batches_count": len(raw_batches),
        "status_counts": build_status_counts(items),
        "missing_metadata_cnl_nums": missing_metadata_nums,
        "items": items,
    }


@router.get("/alerts")
async def get_alerts(
    category: str | None = Query(
        default=None,
        description="Optional category filter, e.g. flow, level, quality.",
    ),
    severity: str | None = Query(
        default=None,
        description="Optional severity filter: critical, warning, unknown, normal.",
    ),
    include_normal: bool = Query(
        default=False,
        description="Include normal channel evaluations. Default returns active alerts only.",
    ),
) -> dict[str, Any]:
    """Return active operational alerts sorted by severity."""
    try:
        snapshot = await build_current_snapshot()
        alerts = evaluate_channels(
            snapshot["items"],
            include_normal=include_normal or severity == "normal",
        )

        if category:
            alerts = [alert for alert in alerts if alert.get("category") == category]

        if severity:
            alerts = [alert for alert in alerts if alert.get("severity") == severity]

        return {
            "ok": True,
            "fetched_at": snapshot["fetched_at"],
            "alerts_count": len(alerts),
            "alerts": alerts,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScadaApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/overview")
async def get_overview() -> dict[str, Any]:
    """Return operational overview summary based on the rules engine."""
    try:
        snapshot = await build_current_snapshot()
        overview = build_overview(
            channels=snapshot["items"],
            fetched_at=snapshot["fetched_at"],
        )

        return {
            "ok": True,
            **overview,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScadaApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc