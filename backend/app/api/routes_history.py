from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.analytics.categories import build_channel_classification
from app.api.routes_current import expand_cnl_nums, get_channel_num, load_metadata_channels
from app.history.sqlite_repository import (
    build_channel_statistics,
    build_statistics_summary_for_channels,
    fetch_history_points,
    get_database_info,
    open_history_db,
)
import traceback


history_router = APIRouter(prefix="/api/history", tags=["history"])
statistics_router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@history_router.get("/db/info")
def get_history_db_info() -> dict[str, Any]:
    """Return local history SQLite database information."""
    try:
        with open_history_db() as conn:
            info = get_database_info(conn)

        return {
            "ok": True,
            "source": "sqlite",
            **info,
        }

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@history_router.get("/{cnl_num}")
def get_channel_history(
    cnl_num: int,
    period: str = Query(
        default="24h",
        description="History period, e.g. 24h, 7d, 30d.",
    ),
    max_points: int = Query(
        default=2000,
        ge=100,
        le=10000,
        description="Maximum returned points. Large periods are downsampled.",
    ),
) -> dict[str, Any]:
    """Return historical values for one channel from local SQLite."""
    try:
        with open_history_db() as conn:
            result = fetch_history_points(
                conn=conn,
                cnl_num=cnl_num,
                period=period,
                max_points=max_points,
            )

        return {
            "ok": True,
            **result,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@statistics_router.get("/summary")
@statistics_router.get("/summary")
def get_statistics_summary(
    cnl_nums: str | None = Query(
        default=None,
        description="Optional channel numbers, e.g. 101,102,200. If omitted, all active channels are used.",
    ),
    category: str | None = Query(
        default=None,
        description="Optional category filter, e.g. flow, level, cumulative_flow.",
    ),
) -> dict[str, Any]:
    """Return compact batch statistics for many dashboard cards."""
    try:
        metadata_channels = load_metadata_channels(active_only=True)

        metadata_by_cnl_num = {
            get_channel_num(channel): channel
            for channel in metadata_channels
            if get_channel_num(channel) is not None
        }

        if cnl_nums:
            requested_nums = expand_cnl_nums(cnl_nums)
        else:
            requested_nums = sorted(metadata_by_cnl_num.keys())

        items_base: list[dict[str, Any]] = []
        eligible_nums: list[int] = []

        for cnl_num in requested_nums:
            channel = metadata_by_cnl_num.get(cnl_num)

            if not channel:
                continue

            category_info = build_channel_classification(channel)

            if category and category_info["category"] != category:
                continue

            eligible_nums.append(cnl_num)

            items_base.append(
                {
                    "cnl_num": cnl_num,
                    "name": channel.get("name"),
                    "display_name": category_info["display_name"],
                    "category": category_info["category"],
                    "category_label": category_info["category_label"],
                    "unit": category_info["unit"],
                    "installation": category_info["installation"],
                }
            )

        with open_history_db() as conn:
            stats_by_cnl_num = build_statistics_summary_for_channels(
                conn=conn,
                cnl_nums=eligible_nums,
            )

        items: list[dict[str, Any]] = []

        for base_item in items_base:
            cnl_num = base_item["cnl_num"]

            stats = stats_by_cnl_num.get(
                cnl_num,
                {
                    "has_history": False,
                    "latest_history_value": None,
                    "latest_history_ts": None,
                    "avg_1h": None,
                    "avg_24h": None,
                    "avg_7d": None,
                    "min_24h": None,
                    "max_24h": None,
                    "delta_1h": None,
                    "delta_24h": None,
                    "delta_3d": None,
                    "deviation_from_avg_1h": None,
                    "deviation_percent_from_avg_1h": None,                     
                },
            )

            items.append(
                {
                    **base_item,
                    **stats,
                }
            )

        return {
            "ok": True,
            "source": "sqlite",
            "mode": "batch_summary",
            "requested_count": len(requested_nums),
            "eligible_count": len(eligible_nums),
            "returned_count": len(items),
            "category_filter": category,
            "items": items,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        print("STATISTICS SUMMARY ERROR")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@statistics_router.get("/{cnl_num}")
def get_channel_statistics(cnl_num: int) -> dict[str, Any]:
    """Return detailed statistics for one channel."""
    try:
        with open_history_db() as conn:
            stats = build_channel_statistics(conn, cnl_num)

        return {
            "ok": True,
            **stats,
        }

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc