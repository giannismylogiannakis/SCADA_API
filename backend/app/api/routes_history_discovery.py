from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.routes_current import expand_cnl_nums
from app.core.config import settings
from app.scada.client import ScadaApiClient, ScadaApiError


router = APIRouter(prefix="/api/history/discovery", tags=["history-discovery"])


def _redact_sensitive_text(text: str) -> str:
    """Redact common sensitive fields from raw previews."""
    patterns = [
        r'("password"\s*:\s*")[^"]+(")',
        r'("Password"\s*:\s*")[^"]+(")',
        r'("token"\s*:\s*")[^"]+(")',
        r'("Token"\s*:\s*")[^"]+(")',
    ]

    redacted = text

    for pattern in patterns:
        redacted = re.sub(pattern, r"\1***\2", redacted, flags=re.IGNORECASE)

    return redacted


def _safe_json_preview(value: Any, max_chars: int) -> str:
    """Convert JSON-compatible data to a compact preview string."""
    try:
        return json.dumps(value, ensure_ascii=False, default=str)[:max_chars]
    except TypeError:
        return str(value)[:max_chars]
    
def _extract_history_shape(parsed: Any) -> dict[str, Any]:
    """Extract basic shape information from a possible GetHistData response."""
    shape: dict[str, Any] = {
        "history_shape_detected": False,
        "history_cnl_nums_count": None,
        "history_timestamps_count": None,
        "history_trend_count": None,
        "history_trend_lengths": [],
        "history_first_timestamp": None,
        "history_last_timestamp": None,
        "history_first_values": [],
    }

    if not isinstance(parsed, dict):
        return shape

    data = parsed.get("data")

    if not isinstance(data, dict):
        return shape

    cnl_nums = data.get("cnlNums")
    timestamps = data.get("timestamps")
    trends = data.get("trends")

    if not (
        isinstance(cnl_nums, list)
        or isinstance(timestamps, list)
        or isinstance(trends, list)
    ):
        return shape

    shape["history_shape_detected"] = True

    if isinstance(cnl_nums, list):
        shape["history_cnl_nums_count"] = len(cnl_nums)

    if isinstance(timestamps, list):
        shape["history_timestamps_count"] = len(timestamps)

        if timestamps:
            shape["history_first_timestamp"] = timestamps[0]
            shape["history_last_timestamp"] = timestamps[-1]

    if isinstance(trends, list):
        shape["history_trend_count"] = len(trends)
        shape["history_trend_lengths"] = [
            len(trend) if isinstance(trend, list) else None
            for trend in trends
        ]
        shape["history_first_values"] = [
            trend[0] if isinstance(trend, list) and trend else None
            for trend in trends
        ]

    return shape


def _summarize_response(
    *,
    candidate: dict[str, Any],
    status_code: int,
    headers: dict[str, str],
    text: str,
    max_preview_chars: int,
) -> dict[str, Any]:
    """Build a safe summary of an HTTP response without assuming its schema."""
    content_type = headers.get("content-type") or headers.get("Content-Type")
    content_length = headers.get("content-length") or headers.get("Content-Length")

    result: dict[str, Any] = {
        "candidate_id": candidate["candidate_id"],
        "description": candidate["description"],
        "method": "GET",
        "path": candidate["path"],
        "params": candidate["params"],
        "http_status": status_code,
        "content_type": content_type,
        "content_length": content_length,
        "looks_like_json": False,
        "json_top_level_type": None,
        "json_keys": [],
        "ok_field": None,
        "msg_field": None,
        "data_type": None,
        "data_count": None,
        "raw_preview": None,
        "error": None,
        "history_shape_detected": False,
        "history_cnl_nums_count": None,
        "history_timestamps_count": None,
        "history_trend_count": None,
        "history_trend_lengths": [],
        "history_first_timestamp": None,
        "history_last_timestamp": None,
        "history_first_values": [],
    }

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        result["raw_preview"] = _redact_sensitive_text(text[:max_preview_chars])
        return result

    result["looks_like_json"] = True
    result["json_top_level_type"] = type(parsed).__name__
    result.update(_extract_history_shape(parsed))

    if isinstance(parsed, dict):
        result["json_keys"] = list(parsed.keys())
        result["ok_field"] = parsed.get("ok")
        result["msg_field"] = parsed.get("msg") or parsed.get("message") or parsed.get("Message")

        data = parsed.get("data")
        result["data_type"] = type(data).__name__ if data is not None else None

        if isinstance(data, list):
            result["data_count"] = len(data)
        elif isinstance(data, dict):
            result["data_count"] = len(data)

    elif isinstance(parsed, list):
        result["data_type"] = "list"
        result["data_count"] = len(parsed)

    result["raw_preview"] = _redact_sensitive_text(
        _safe_json_preview(parsed, max_preview_chars)
    )

    return result


def _build_candidate_requests(
    *,
    cnl_nums_text: str,
    first_cnl_num: int,
    start_time: str,
    end_time: str,
    archive_code: str,
) -> list[dict[str, Any]]:
    """Build conservative read-only GET candidates for Rapid SCADA history discovery."""
    return [
        {
            "candidate_id": "current_control",
            "description": "Known working current-data endpoint, used only to verify login/session.",
            "path": "Api/Main/GetCurData",
            "params": {
                "cnlNums": cnl_nums_text,
            },
        },
        {
            "candidate_id": "hist_data_cnl_nums_archive_code",
            "description": "Possible historical endpoint using cnlNums, startTime, endTime and archiveCode.",
            "path": "Api/Main/GetHistData",
            "params": {
                "cnlNums": cnl_nums_text,
                "startTime": start_time,
                "endTime": end_time,
                "archiveCode": archive_code,
            },
        },
        {
            "candidate_id": "hist_data_single_cnl_archive_code",
            "description": "Possible historical endpoint using single cnlNum, startTime, endTime and archiveCode.",
            "path": "Api/Main/GetHistData",
            "params": {
                "cnlNum": first_cnl_num,
                "startTime": start_time,
                "endTime": end_time,
                "archiveCode": archive_code,
            },
        },
        {
            "candidate_id": "arc_data_cnl_nums_archive_code",
            "description": "Possible archive-data endpoint using cnlNums, startTime, endTime and archiveCode.",
            "path": "Api/Main/GetArcData",
            "params": {
                "cnlNums": cnl_nums_text,
                "startTime": start_time,
                "endTime": end_time,
                "archiveCode": archive_code,
            },
        },
        {
            "candidate_id": "archive_data_cnl_nums_archive_code",
            "description": "Possible archive-data endpoint using cnlNums, startTime, endTime and archiveCode.",
            "path": "Api/Main/GetArchiveData",
            "params": {
                "cnlNums": cnl_nums_text,
                "startTime": start_time,
                "endTime": end_time,
                "archiveCode": archive_code,
            },
        },
        {
            "candidate_id": "trend_single_cnl_archive_code",
            "description": "Possible trend endpoint using single cnlNum, startTime, endTime and archiveCode.",
            "path": "Api/Main/GetTrend",
            "params": {
                "cnlNum": first_cnl_num,
                "startTime": start_time,
                "endTime": end_time,
                "archiveCode": archive_code,
            },
        },
        {
            "candidate_id": "trend_data_single_cnl_archive_code",
            "description": "Possible trend-data endpoint using single cnlNum, startTime, endTime and archiveCode.",
            "path": "Api/Main/GetTrendData",
            "params": {
                "cnlNum": first_cnl_num,
                "startTime": start_time,
                "endTime": end_time,
                "archiveCode": archive_code,
            },
        },
    ]


@router.get("/probe")
async def probe_history_endpoints(
    cnl_nums: str = Query(
        ...,
        description="One or two test channel numbers, e.g. 101,200.",
    ),
    period_hours: int = Query(
        default=24,
        ge=1,
        le=720,
        description="How many hours back to request. Default: 24.",
    ),
    archive_code: str = Query(
        default="Min",
        description="Candidate archive code/name, e.g. Min, Hour or Day.",
    ),
    max_candidates: int = Query(
        default=7,
        ge=1,
        le=20,
        description="Maximum number of candidate requests to execute.",
    ),
    max_preview_chars: int = Query(
        default=2000,
        ge=200,
        le=10000,
        description="Maximum raw preview characters per response.",
    ),
) -> dict[str, Any]:
    """
    Probe possible Rapid SCADA historical endpoints using read-only GET requests.

    This endpoint is intentionally exploratory. It does not parse or trust
    any historical response format yet.
    """
    try:
        cnl_nums_list = expand_cnl_nums(cnl_nums)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not cnl_nums_list:
        raise HTTPException(status_code=400, detail="Δεν δόθηκαν έγκυρα κανάλια.")

    selected_nums = cnl_nums_list[:2]
    selected_nums_text = ",".join(str(num) for num in selected_nums)

    end_dt = datetime.now(timezone.utc).replace(microsecond=0)
    start_dt = end_dt - timedelta(hours=period_hours)

    start_time = start_dt.isoformat()
    end_time = end_dt.isoformat()

    candidates = _build_candidate_requests(
        cnl_nums_text=selected_nums_text,
        first_cnl_num=selected_nums[0],
        start_time=start_time,
        end_time=end_time,
        archive_code=archive_code,
    )[:max_candidates]

    results: list[dict[str, Any]] = []

    try:
        async with ScadaApiClient(
            base_url=settings.scada_base_url,
            username=settings.scada_username,
            password=settings.scada_password,
            timeout_seconds=settings.scada_request_timeout_seconds,
        ) as client:
            login_result = await client.login()

            for candidate in candidates:
                try:
                    response = await client.get_raw(
                        candidate["path"],
                        params=candidate["params"],
                    )

                    results.append(
                        _summarize_response(
                            candidate=candidate,
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            text=response.text,
                            max_preview_chars=max_preview_chars,
                        )
                    )
                except ScadaApiError as exc:
                    failed = dict(candidate)
                    failed["method"] = "GET"
                    failed["http_status"] = None
                    failed["error"] = str(exc)
                    results.append(failed)

            logout_result = await client.logout()

    except ScadaApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    likely_candidates = [
        item
        for item in results
        if item.get("http_status") == 200
        and item.get("looks_like_json") is True
        and item.get("candidate_id") != "current_control"
    ]

    return {
        "ok": True,
        "mode": "read_only_discovery",
        "important_note": (
            "Τα αποτελέσματα είναι raw discovery. Δεν θεωρούμε ακόμα ότι βρήκαμε "
            "σωστό historical format μέχρι να δούμε δείγμα response."
        ),
        "selected_cnl_nums": selected_nums,
        "period_hours": period_hours,
        "archive_code": archive_code,
        "start_time_utc": start_time,
        "end_time_utc": end_time,
        "login_ok": bool(login_result),
        "logout_ok": logout_result is not None,
        "candidate_count": len(candidates),
        "likely_candidate_count": len(likely_candidates),
        "likely_candidate_ids": [
            item.get("candidate_id") for item in likely_candidates
        ],
        "results": results,
    }