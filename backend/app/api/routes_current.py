from datetime import datetime, timezone
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.metadata.xml_loader import load_channels_metadata
from app.metadata.status_loader import load_cnl_statuses
from app.scada.client import ScadaApiClient, ScadaApiError

router = APIRouter(prefix="/api/current", tags=["current"])

_CNL_NUMS_PATTERN = re.compile(r"^[0-9,\-\s]+$")
DEFAULT_BATCH_SIZE = 50


def normalize_cnl_nums(cnl_nums: str) -> str:
    """Validate and normalize channel number list/ranges."""
    value = cnl_nums.strip().replace(" ", "")

    if not value:
        raise ValueError("Το cnl_nums είναι κενό.")

    if not _CNL_NUMS_PATTERN.match(value):
        raise ValueError(
            "Το cnl_nums επιτρέπεται να περιέχει μόνο αριθμούς, κόμμα και παύλα."
        )

    return value


def expand_cnl_nums(cnl_nums: str) -> list[int]:
    """Convert cnl_nums string like '101,102,105-107' to a list of integers."""
    normalized = normalize_cnl_nums(cnl_nums)
    result: list[int] = []

    for part in normalized.split(","):
        if not part:
            continue

        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start = int(start_text)
            end = int(end_text)

            if end < start:
                raise ValueError(f"Λάθος range καναλιών: {part}")

            result.extend(range(start, end + 1))
        else:
            result.append(int(part))

    return sorted(set(result))


def batch_items(items: list[int], batch_size: int = DEFAULT_BATCH_SIZE) -> list[list[int]]:
    """Split items into smaller batches."""
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def to_plain_dict(value: Any) -> dict[str, Any]:
    """Convert Pydantic/dataclass/plain object to dictionary."""
    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    if hasattr(value, "__dict__"):
        return dict(value.__dict__)

    raise TypeError(f"Unsupported metadata object type: {type(value)}")


def is_active_channel(channel: dict[str, Any]) -> bool:
    """Check if a metadata channel is active."""
    active = channel.get("active")

    if isinstance(active, bool):
        return active

    if isinstance(active, int):
        return active == 1

    if isinstance(active, str):
        return active.strip().lower() in {"true", "1", "yes", "y"}

    return False


def load_metadata_channels(active_only: bool = True) -> list[dict[str, Any]]:
    """
    Load channel metadata from the existing XML loader.

    If the existing loader supports active_only, use it.
    Otherwise, load all channels and filter here.
    """
    try:
        channels = load_channels_metadata(active_only=active_only)
    except TypeError:
        channels = load_channels_metadata()

    metadata = [to_plain_dict(channel) for channel in channels]

    if active_only:
        metadata = [channel for channel in metadata if is_active_channel(channel)]

    return metadata


def get_channel_num(channel: dict[str, Any]) -> int | None:
    """Read channel number from metadata with tolerant field names."""
    value = channel.get("cnl_num", channel.get("cnlNum"))

    if value is None:
        return None

    return int(value)


def get_scada_status_info(stat: Any) -> dict[str, Any]:
    """Get Rapid SCADA status details from CnlStatus.xml."""
    if stat is None:
        return {
            "id": None,
            "name": "No data",
            "main_color": None,
            "second_color": None,
            "back_color": None,
            "severity": None,
            "ack_required": False,
            "description": "No current data returned for this channel.",
        }

    try:
        stat_int = int(stat)
    except (TypeError, ValueError):
        return {
            "id": None,
            "name": str(stat),
            "main_color": None,
            "second_color": None,
            "back_color": None,
            "severity": None,
            "ack_required": False,
            "description": "Unknown non-numeric SCADA status.",
        }

    statuses = load_cnl_statuses()
    status = statuses.get(stat_int)

    if status:
        return status

    return {
        "id": stat_int,
        "name": f"Status {stat_int}",
        "main_color": None,
        "second_color": None,
        "back_color": None,
        "severity": None,
        "ack_required": False,
        "description": "Unknown SCADA status ID.",
    }


def describe_scada_status(stat: Any) -> str:
    """Return status name for backward-compatible current parsing."""
    return get_scada_status_info(stat)["name"]


def parse_current_data(raw_response: Any) -> dict[int, dict[str, Any]]:
    """Parse Rapid SCADA GetCurData response into dictionary by channel number."""
    if not isinstance(raw_response, dict):
        raise ValueError("Το Rapid SCADA επέστρεψε απροσδόκητο response format.")

    if raw_response.get("ok") is not True:
        raise ValueError(
            "Το Rapid SCADA GetCurData επέστρεψε ok=false. "
            f"Message: {raw_response.get('msg', '')}"
        )

    data = raw_response.get("data")

    if not isinstance(data, list):
        raise ValueError("Το Rapid SCADA response δεν περιέχει λίστα data.")

    result: dict[int, dict[str, Any]] = {}

    for item in data:
        if not isinstance(item, dict):
            continue

        cnl_num = item.get("cnlNum")
        if cnl_num is None:
            continue

        cnl_num_int = int(cnl_num)

        result[cnl_num_int] = {
            "cnl_num": cnl_num_int,
            "current_value": item.get("val"),
            "scada_status": item.get("stat"),
            "scada_status_text": describe_scada_status(item.get("stat")),
            "raw": item,
        }

    return result


def merge_current_with_metadata(
    metadata_channels: list[dict[str, Any]],
    current_by_cnl_num: dict[int, dict[str, Any]],
    include_raw: bool = False,
) -> list[dict[str, Any]]:
    """Merge XML metadata with current values from Rapid SCADA."""
    merged: list[dict[str, Any]] = []

    for channel in metadata_channels:
        cnl_num = get_channel_num(channel)

        if cnl_num is None:
            continue

        current = current_by_cnl_num.get(cnl_num)
        status_code = current.get("scada_status") if current else None
        status_info = get_scada_status_info(status_code)

        item = {
            "cnl_num": cnl_num,
            "active": channel.get("active"),
            "name": channel.get("name"),
            "tag_code": channel.get("tag_code"),
            "device_num": channel.get("device_num"),
            "device_name": channel.get("device_name"),
            "comm_line_num": channel.get("comm_line_num"),
            "comm_line_name": channel.get("comm_line_name"),
            "cnl_type_id": channel.get("cnl_type_id"),
            "format_id": channel.get("format_id"),
            "unit_id": channel.get("unit_id"),
            "current_value": current.get("current_value") if current else None,
            "scada_status": status_code,
            "scada_status_text": status_info["name"],
            "scada_status_description": status_info["description"],
            "scada_status_severity": status_info["severity"],
            "scada_status_ack_required": status_info["ack_required"],
            "scada_status_color": status_info["main_color"],
            "scada_status_back_color": status_info["back_color"],
            "last_update": None,
        }

        if include_raw:
            item["raw_metadata"] = channel
            item["raw_current"] = current.get("raw") if current else None

        merged.append(item)

    return merged

def build_status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    """Count channels by SCADA status text."""
    counts: dict[str, int] = {}

    for item in items:
        status_text = item.get("scada_status_text") or "Unknown"
        counts[status_text] = counts.get(status_text, 0) + 1

    return counts

@router.get("/raw")
async def get_current_raw(
    cnl_nums: str = Query(
        ...,
        description="Channel numbers, e.g. 101,102,103 or 101-105,110",
    )
) -> dict[str, Any]:
    """
    Debug endpoint for reading raw Rapid SCADA current data.

    This endpoint intentionally returns the raw API response.
    """
    try:
        normalized_cnl_nums = normalize_cnl_nums(cnl_nums)

        async with ScadaApiClient(
            base_url=settings.scada_base_url,
            username=settings.scada_username,
            password=settings.scada_password,
            timeout_seconds=settings.scada_request_timeout_seconds,
        ) as client:
            login_result = await client.login()
            raw_current_data = await client.get_current_data(normalized_cnl_nums)
            logout_result = await client.logout()

        return {
            "requested_cnl_nums": normalized_cnl_nums,
            "login_result": login_result,
            "raw_current_data": raw_current_data,
            "logout_result": logout_result,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScadaApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("")
async def get_current(
    cnl_nums: str | None = Query(
        default=None,
        description="Optional channel numbers, e.g. 101,102,103. If omitted, all active channels are used.",
    ),
    include_raw: bool = Query(
        default=False,
        description="Include raw SCADA and metadata fields for debugging.",
    ),
) -> dict[str, Any]:
    """
    Read current values and merge them with XML metadata.

    Without cnl_nums, all active metadata channels are requested.
    With cnl_nums, only those channels are requested.
    """
    fetched_at = datetime.now(timezone.utc).isoformat()

    try:
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
            include_raw=include_raw,
        )

        response = {
        "ok": True,
        "fetched_at": fetched_at,
        "requested_count": len(requested_nums),
        "returned_count": len(current_by_cnl_num),
        "batches_count": len(raw_batches),
        "status_counts": build_status_counts(items),
        "missing_metadata_cnl_nums": missing_metadata_nums,
        "items": items,
            }   

        if include_raw:
            response["raw_batches"] = raw_batches

        return response

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScadaApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc