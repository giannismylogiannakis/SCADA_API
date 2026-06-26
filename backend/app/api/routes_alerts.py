from __future__ import annotations

import asyncio
import time
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
from app.history.sqlite_repository import (
    build_statistics_summary_for_channels,
    open_history_db,
)
from app.scada.client import ScadaApiClient, ScadaApiError


router = APIRouter(prefix="/api", tags=["alerts"])

# One shared Rapid SCADA HTTP client/session for this backend process.
# This avoids login/logout on every dashboard refresh.
_shared_scada_client: ScadaApiClient | None = None
_shared_scada_lock = asyncio.Lock()

# One snapshot cache for the dashboard. The rules engine is fast; the slow part is
# reading all current values from Rapid SCADA. Cache prevents duplicate refresh storms.
_snapshot_cache: dict[str, Any] | None = None
_snapshot_cache_key: str | None = None
_snapshot_cache_saved_at: float = 0.0
_snapshot_lock = asyncio.Lock()

SNAPSHOT_CACHE_TTL_SECONDS = 60.0

def clear_dashboard_snapshot_cache() -> None:
    """Clear cached dashboard snapshot after local settings changes."""
    global _snapshot_cache
    global _snapshot_cache_key
    global _snapshot_cache_saved_at

    _snapshot_cache = None
    _snapshot_cache_key = None
    _snapshot_cache_saved_at = 0.0


async def reset_shared_scada_client() -> None:
    """Close and forget the shared SCADA client/session."""
    global _shared_scada_client

    async with _shared_scada_lock:
        if _shared_scada_client is not None:
            try:
                await _shared_scada_client.close()
            except Exception:
                pass

        _shared_scada_client = None


async def get_shared_scada_client() -> ScadaApiClient:
    """
    Return a shared logged-in Rapid SCADA client.

    If the server session expires, the caller can reset and retry once.
    """
    global _shared_scada_client

    async with _shared_scada_lock:
        if _shared_scada_client is None:
            client = ScadaApiClient(
                base_url=settings.scada_base_url,
                username=settings.scada_username,
                password=settings.scada_password,
                timeout_seconds=settings.scada_request_timeout_seconds,
            )
            await client.login()
            _shared_scada_client = client

        return _shared_scada_client


async def get_current_data_with_retry(cnl_nums_query: str) -> Any:
    """
    Read current data using the shared SCADA session.

    Retry once with a fresh login if the existing session is no longer valid.
    """
    last_error: ScadaApiError | None = None

    for attempt in range(2):
        client = await get_shared_scada_client()

        try:
            return await client.get_current_data(cnl_nums_query)
        except ScadaApiError as exc:
            last_error = exc
            await reset_shared_scada_client()

            if attempt == 1:
                raise

    if last_error:
        raise last_error

    raise ScadaApiError("Αποτυχία ανάγνωσης current data από Rapid SCADA.")


def attach_statistics_to_channels(channels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach local SQLite statistics to current channels when available."""
    cnl_nums = [
        int(channel["cnl_num"])
        for channel in channels
        if channel.get("cnl_num") is not None
    ]

    if not cnl_nums:
        return channels

    try:
        with open_history_db() as conn:
            stats_by_cnl_num = build_statistics_summary_for_channels(
                conn=conn,
                cnl_nums=cnl_nums,
            )
    except FileNotFoundError:
        return channels

    for channel in channels:
        cnl_num = channel.get("cnl_num")
        channel["statistics"] = (
            stats_by_cnl_num.get(int(cnl_num), {})
            if cnl_num is not None
            else {}
        )

    return channels


def make_snapshot_cache_key(cnl_nums: str | None) -> str:
    """Build a cache key for a current snapshot request."""
    return cnl_nums.strip() if cnl_nums else "__all_active_channels__"


async def build_fresh_current_snapshot(
    cnl_nums: str | None = None,
) -> dict[str, Any]:
    """Read current values from SCADA, merge metadata, and attach SQLite stats."""
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

    for batch in batch_items(requested_nums):
        batch_query = ",".join(str(num) for num in batch)
        raw_response = await get_current_data_with_retry(batch_query)
        raw_batches.append(raw_response)

        parsed_batch = parse_current_data(raw_response)
        current_by_cnl_num.update(parsed_batch)

    items = merge_current_with_metadata(
        metadata_channels=metadata_channels,
        current_by_cnl_num=current_by_cnl_num,
        include_raw=False,
    )

    for item in items:
        item["fetched_at"] = fetched_at

    attach_statistics_to_channels(items)

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


async def build_current_snapshot(
    cnl_nums: str | None = None,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Return current snapshot.

    Uses a short cache so multiple frontend/backend calls do not hammer Rapid SCADA.
    """
    global _snapshot_cache
    global _snapshot_cache_key
    global _snapshot_cache_saved_at

    cache_key = make_snapshot_cache_key(cnl_nums)
    now = time.monotonic()

    if (
        not force_refresh
        and _snapshot_cache is not None
        and _snapshot_cache_key == cache_key
        and now - _snapshot_cache_saved_at <= SNAPSHOT_CACHE_TTL_SECONDS
    ):
        cached_snapshot = dict(_snapshot_cache)
        cached_snapshot["cache"] = {
            "hit": True,
            "age_seconds": round(now - _snapshot_cache_saved_at, 3),
            "ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
        }
        return cached_snapshot

    async with _snapshot_lock:
        now = time.monotonic()

        if (
            not force_refresh
            and _snapshot_cache is not None
            and _snapshot_cache_key == cache_key
            and now - _snapshot_cache_saved_at <= SNAPSHOT_CACHE_TTL_SECONDS
        ):
            cached_snapshot = dict(_snapshot_cache)
            cached_snapshot["cache"] = {
                "hit": True,
                "age_seconds": round(now - _snapshot_cache_saved_at, 3),
                "ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
            }
            return cached_snapshot

        fresh_snapshot = await build_fresh_current_snapshot(cnl_nums=cnl_nums)

        _snapshot_cache = fresh_snapshot
        _snapshot_cache_key = cache_key
        _snapshot_cache_saved_at = time.monotonic()

        fresh_snapshot["cache"] = {
            "hit": False,
            "age_seconds": 0,
            "ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
        }

        return fresh_snapshot


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
    force_refresh: bool = Query(
        default=False,
        description="Bypass snapshot cache and read fresh values from Rapid SCADA.",
    ),
) -> dict[str, Any]:
    """Return active operational alerts sorted by severity."""
    try:
        snapshot = await build_current_snapshot(force_refresh=force_refresh)
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
            "cache": snapshot.get("cache"),
            "alerts_count": len(alerts),
            "alerts": alerts,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScadaApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/overview")
async def get_overview(
    force_refresh: bool = Query(
        default=False,
        description="Bypass snapshot cache and read fresh values from Rapid SCADA.",
    ),
) -> dict[str, Any]:
    """Return operational overview summary based on the rules engine."""
    try:
        snapshot = await build_current_snapshot(force_refresh=force_refresh)
        overview = build_overview(
            channels=snapshot["items"],
            fetched_at=snapshot["fetched_at"],
        )

        return {
            "ok": True,
            "cache": snapshot.get("cache"),
            **overview,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScadaApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc