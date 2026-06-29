from __future__ import annotations

import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings


_PERIOD_PATTERN = re.compile(r"^(\d+)(h|d)$", re.IGNORECASE)


def round_float(value: Any, digits: int = 3) -> float | None:
    """Round numeric values safely."""
    if value is None:
        return None

    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def parse_period(period: str) -> timedelta:
    """Parse period strings like 24h, 7d, 30d."""
    match = _PERIOD_PATTERN.match(period.strip())

    if not match:
        raise ValueError("Το period πρέπει να είναι π.χ. 24h, 7d ή 30d.")

    amount = int(match.group(1))
    unit = match.group(2).lower()

    if amount <= 0:
        raise ValueError("Το period πρέπει να είναι θετικό.")

    if unit == "h":
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)

    if delta > timedelta(days=90):
        raise ValueError("Για λόγους απόδοσης, το μέγιστο period είναι 90d.")

    return delta


def parse_iso_ts(value: str) -> datetime:
    """Parse ISO timestamp stored in SQLite."""
    return datetime.fromisoformat(value)


def resolve_db_path() -> Path:
    """Resolve SQLite DB path from settings."""
    path = Path(settings.scada_history_sqlite_path)

    if not path.is_absolute():
        path = Path.cwd() / path

    return path


@contextmanager
def open_history_db() -> Iterator[sqlite3.Connection]:
    """Open local history SQLite database in read-only mode."""
    db_path = resolve_db_path()

    if not db_path.exists():
        raise FileNotFoundError(f"History SQLite database not found: {db_path}")

    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA query_only = ON;")
        yield conn
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert sqlite row to dict."""
    if row is None:
        return None

    return dict(row)


def get_database_info(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return basic information about the local history database."""
    imports = [
        dict(row)
        for row in conn.execute(
            """
            SELECT *
            FROM history_imports
            ORDER BY imported_at DESC
            """
        )
    ]

    values_count = conn.execute(
        "SELECT COUNT(*) FROM history_values"
    ).fetchone()[0]

    channels_count = conn.execute(
        "SELECT COUNT(DISTINCT cnl_num) FROM history_values"
    ).fetchone()[0]

    min_ts, max_ts = conn.execute(
        "SELECT MIN(ts), MAX(ts) FROM history_values"
    ).fetchone()

    channel_samples = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                cnl_num,
                COUNT(*) AS samples_count,
                MIN(ts) AS first_ts,
                MAX(ts) AS last_ts
            FROM history_values
            GROUP BY cnl_num
            ORDER BY cnl_num
            LIMIT 20
            """
        )
    ]

    return {
        "db_path": str(resolve_db_path()),
        "imports": imports,
        "values_count": values_count,
        "channels_count": channels_count,
        "first_ts": min_ts,
        "last_ts": max_ts,
        "channel_samples": channel_samples,
    }


def get_latest_value(
    conn: sqlite3.Connection,
    cnl_num: int,
) -> dict[str, Any] | None:
    """Return the latest historical value of one channel."""
    row = conn.execute(
        """
        SELECT cnl_num, ts, val, stat, source
        FROM history_values
        WHERE cnl_num = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (cnl_num,),
    ).fetchone()

    return row_to_dict(row)


def get_first_value_in_range(
    conn: sqlite3.Connection,
    cnl_num: int,
    start_ts: str,
    end_ts: str,
) -> dict[str, Any] | None:
    """Return the first value inside a time range."""
    row = conn.execute(
        """
        SELECT cnl_num, ts, val, stat, source
        FROM history_values
        WHERE cnl_num = ?
          AND ts >= ?
          AND ts <= ?
        ORDER BY ts
        LIMIT 1
        """,
        (cnl_num, start_ts, end_ts),
    ).fetchone()

    return row_to_dict(row)


def aggregate_range(
    conn: sqlite3.Connection,
    cnl_num: int,
    start_ts: str,
    end_ts: str,
) -> dict[str, Any]:
    """Aggregate values for one channel inside a time range."""
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS sample_count,
            AVG(val) AS avg_value,
            MIN(val) AS min_value,
            MAX(val) AS max_value,
            MIN(ts) AS first_ts,
            MAX(ts) AS last_ts
        FROM history_values
        WHERE cnl_num = ?
          AND ts >= ?
          AND ts <= ?
          AND val IS NOT NULL
        """,
        (cnl_num, start_ts, end_ts),
    ).fetchone()

    result = dict(row)

    return {
        "sample_count": result["sample_count"],
        "avg": round_float(result["avg_value"]),
        "min": round_float(result["min_value"]),
        "max": round_float(result["max_value"]),
        "first_ts": result["first_ts"],
        "last_ts": result["last_ts"],
    }


def aggregate_same_hour_previous_7d(
    conn: sqlite3.Connection,
    cnl_num: int,
    end_dt: datetime,
) -> dict[str, Any]:
    """Aggregate values from the same hour during the previous 7 days."""
    start_dt = end_dt - timedelta(days=7)
    hour_text = f"{end_dt.hour:02d}"
    current_day = end_dt.date().isoformat()

    row = conn.execute(
        """
        SELECT
            COUNT(*) AS sample_count,
            AVG(val) AS avg_value,
            MIN(val) AS min_value,
            MAX(val) AS max_value,
            MIN(ts) AS first_ts,
            MAX(ts) AS last_ts
        FROM history_values
        WHERE cnl_num = ?
          AND ts >= ?
          AND ts < ?
          AND substr(ts, 12, 2) = ?
          AND substr(ts, 1, 10) < ?
          AND val IS NOT NULL
        """,
        (
            cnl_num,
            start_dt.isoformat(timespec="seconds"),
            end_dt.isoformat(timespec="seconds"),
            hour_text,
            current_day,
        ),
    ).fetchone()

    result = dict(row)

    return {
        "sample_count": result["sample_count"],
        "avg": round_float(result["avg_value"]),
        "min": round_float(result["min_value"]),
        "max": round_float(result["max_value"]),
        "first_ts": result["first_ts"],
        "last_ts": result["last_ts"],
    }


def fetch_history_points(
    conn: sqlite3.Connection,
    cnl_num: int,
    period: str,
    max_points: int,
) -> dict[str, Any]:
    """Fetch historical points for one channel, optionally downsampled."""
    latest = get_latest_value(conn, cnl_num)

    if latest is None:
        return {
            "cnl_num": cnl_num,
            "period": period,
            "source": "sqlite",
            "latest_ts": None,
            "start_ts": None,
            "total_points": 0,
            "returned_points": 0,
            "downsampled": False,
            "items": [],
        }

    delta = parse_period(period)
    end_dt = parse_iso_ts(latest["ts"])
    start_dt = end_dt - delta

    start_ts = start_dt.isoformat(timespec="seconds")
    end_ts = end_dt.isoformat(timespec="seconds")

    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT cnl_num, ts, val, stat, source
            FROM history_values
            WHERE cnl_num = ?
              AND ts >= ?
              AND ts <= ?
            ORDER BY ts
            """,
            (cnl_num, start_ts, end_ts),
        )
    ]

    total_points = len(rows)
    downsampled = False

    if max_points > 0 and total_points > max_points:
        step = max(1, math.ceil(total_points / max_points))
        rows = rows[::step]
        downsampled = True

    return {
        "cnl_num": cnl_num,
        "period": period,
        "source": "sqlite",
        "latest_ts": end_ts,
        "start_ts": start_ts,
        "total_points": total_points,
        "returned_points": len(rows),
        "downsampled": downsampled,
        "items": rows,
    }


def build_channel_statistics(
    conn: sqlite3.Connection,
    cnl_num: int,
) -> dict[str, Any]:
    """Build useful statistics for one channel."""
    latest = get_latest_value(conn, cnl_num)

    if latest is None:
        return {
            "cnl_num": cnl_num,
            "source": "sqlite",
            "has_history": False,
            "latest": None,
            "periods": {},
            "same_hour_previous_7d": None,
            "deviation_from_same_hour_avg": None,
            "deviation_percent_from_same_hour_avg": None,
            "deltas": {},
        }

    end_dt = parse_iso_ts(latest["ts"])
    latest_value = latest["val"]

    periods: dict[str, dict[str, Any]] = {}

    for period_name, delta in {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "3d": timedelta(days=3),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }.items():
        start_dt = end_dt - delta
        periods[period_name] = aggregate_range(
            conn=conn,
            cnl_num=cnl_num,
            start_ts=start_dt.isoformat(timespec="seconds"),
            end_ts=end_dt.isoformat(timespec="seconds"),
        )

    same_hour = aggregate_same_hour_previous_7d(
        conn=conn,
        cnl_num=cnl_num,
        end_dt=end_dt,
    )

    same_hour_avg = same_hour.get("avg")
    deviation = None
    deviation_percent = None

    if latest_value is not None and same_hour_avg not in (None, 0):
        deviation = round_float(float(latest_value) - float(same_hour_avg))
        deviation_percent = round_float(
            ((float(latest_value) - float(same_hour_avg)) / float(same_hour_avg)) * 100
        )

    deltas: dict[str, dict[str, Any]] = {}

    for period_name, delta in {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "3d": timedelta(days=3),
    }.items():
        start_dt = end_dt - delta
        first = get_first_value_in_range(
            conn=conn,
            cnl_num=cnl_num,
            start_ts=start_dt.isoformat(timespec="seconds"),
            end_ts=end_dt.isoformat(timespec="seconds"),
        )

        if first and first["val"] is not None and latest_value is not None:
            delta_value = round_float(float(latest_value) - float(first["val"]))
        else:
            delta_value = None

        deltas[period_name] = {
            "start_ts": first["ts"] if first else None,
            "start_value": round_float(first["val"]) if first else None,
            "end_ts": latest["ts"],
            "end_value": round_float(latest_value),
            "delta": delta_value,
        }

    return {
        "cnl_num": cnl_num,
        "source": "sqlite",
        "has_history": True,
        "latest": {
            "ts": latest["ts"],
            "val": round_float(latest_value),
            "stat": latest["stat"],
        },
        "periods": periods,
        "same_hour_previous_7d": same_hour,
        "deviation_from_same_hour_avg": deviation,
        "deviation_percent_from_same_hour_avg": deviation_percent,
        "deltas": deltas,
    }

def make_placeholders(values: list[int]) -> str:
    """Create SQL placeholders for an IN clause."""
    return ",".join("?" for _ in values)


def aggregate_period_for_channels(
    conn: sqlite3.Connection,
    cnl_nums: list[int],
    start_ts: str,
    end_ts: str,
) -> dict[int, dict[str, Any]]:
    """Aggregate one period for many channels in one grouped query."""
    if not cnl_nums:
        return {}

    placeholders = make_placeholders(cnl_nums)

    rows = conn.execute(
        f"""
        SELECT
            cnl_num,
            COUNT(*) AS sample_count,
            AVG(val) AS avg_value,
            MIN(val) AS min_value,
            MAX(val) AS max_value,
            MIN(ts) AS first_ts,
            MAX(ts) AS last_ts
        FROM history_values
        WHERE cnl_num IN ({placeholders})
          AND ts >= ?
          AND ts <= ?
          AND val IS NOT NULL
        GROUP BY cnl_num
        """,
        (*cnl_nums, start_ts, end_ts),
    ).fetchall()

    return {
        int(row["cnl_num"]): {
            "sample_count": row["sample_count"],
            "avg": round_float(row["avg_value"]),
            "min": round_float(row["min_value"]),
            "max": round_float(row["max_value"]),
            "first_ts": row["first_ts"],
            "last_ts": row["last_ts"],
        }
        for row in rows
    }


def latest_values_for_channels(
    conn: sqlite3.Connection,
    cnl_nums: list[int],
) -> dict[int, dict[str, Any]]:
    """Return latest historical value for many channels."""
    if not cnl_nums:
        return {}

    placeholders = make_placeholders(cnl_nums)

    rows = conn.execute(
        f"""
        WITH latest AS (
            SELECT
                cnl_num,
                MAX(ts) AS latest_ts
            FROM history_values
            WHERE cnl_num IN ({placeholders})
            GROUP BY cnl_num
        )
        SELECT
            hv.cnl_num,
            hv.ts,
            hv.val,
            hv.stat,
            hv.source
        FROM history_values hv
        INNER JOIN latest l
            ON l.cnl_num = hv.cnl_num
           AND l.latest_ts = hv.ts
        ORDER BY hv.cnl_num
        """,
        tuple(cnl_nums),
    ).fetchall()

    return {
        int(row["cnl_num"]): {
            "cnl_num": row["cnl_num"],
            "ts": row["ts"],
            "val": row["val"],
            "stat": row["stat"],
            "source": row["source"],
        }
        for row in rows
    }


def first_values_for_channels_in_range(
    conn: sqlite3.Connection,
    cnl_nums: list[int],
    start_ts: str,
    end_ts: str,
) -> dict[int, dict[str, Any]]:
    """Return first value per channel inside a time range."""
    if not cnl_nums:
        return {}

    placeholders = make_placeholders(cnl_nums)

    rows = conn.execute(
        f"""
        WITH first_points AS (
            SELECT
                cnl_num,
                MIN(ts) AS first_ts
            FROM history_values
            WHERE cnl_num IN ({placeholders})
              AND ts >= ?
              AND ts <= ?
              AND val IS NOT NULL
            GROUP BY cnl_num
        )
        SELECT
            hv.cnl_num,
            hv.ts,
            hv.val,
            hv.stat,
            hv.source
        FROM history_values hv
        INNER JOIN first_points fp
            ON fp.cnl_num = hv.cnl_num
           AND fp.first_ts = hv.ts
        ORDER BY hv.cnl_num
        """,
        (*cnl_nums, start_ts, end_ts),
    ).fetchall()

    return {
        int(row["cnl_num"]): {
            "cnl_num": row["cnl_num"],
            "ts": row["ts"],
            "val": row["val"],
            "stat": row["stat"],
            "source": row["source"],
        }
        for row in rows
    }


def calculate_delta(
    latest_value: Any,
    first_value: Any,
) -> float | None:
    """Calculate a numeric delta safely."""
    if latest_value is None or first_value is None:
        return None

    try:
        return round_float(float(latest_value) - float(first_value))
    except (TypeError, ValueError):
        return None


def build_statistics_summary_for_channels(
    conn: sqlite3.Connection,
    cnl_nums: list[int],
) -> dict[int, dict[str, Any]]:
    """Build compact dashboard statistics for many channels efficiently."""
    clean_cnl_nums = sorted({int(cnl_num) for cnl_num in cnl_nums})

    if not clean_cnl_nums:
        return {}

    latest_map = latest_values_for_channels(conn, clean_cnl_nums)

    empty_stats = {
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
    }

    if not latest_map:
        return {cnl_num: dict(empty_stats) for cnl_num in clean_cnl_nums}

    latest_ts = max(item["ts"] for item in latest_map.values())
    end_dt = parse_iso_ts(latest_ts)
    end_ts = end_dt.isoformat(timespec="seconds")

    start_1h = (end_dt - timedelta(hours=1)).isoformat(timespec="seconds")
    start_24h = (end_dt - timedelta(hours=24)).isoformat(timespec="seconds")
    start_3d = (end_dt - timedelta(days=3)).isoformat(timespec="seconds")
    start_7d = (end_dt - timedelta(days=7)).isoformat(timespec="seconds")

    # Lightweight dashboard summary:
    # no 30d, no same-hour query, no unnecessary 3d aggregates.
    agg_1h = aggregate_period_for_channels(conn, clean_cnl_nums, start_1h, end_ts)
    agg_24h = aggregate_period_for_channels(conn, clean_cnl_nums, start_24h, end_ts)
    agg_7d = aggregate_period_for_channels(conn, clean_cnl_nums, start_7d, end_ts)

    first_1h = first_values_for_channels_in_range(
        conn, clean_cnl_nums, start_1h, end_ts
    )
    first_24h = first_values_for_channels_in_range(
        conn, clean_cnl_nums, start_24h, end_ts
    )
    first_3d = first_values_for_channels_in_range(
        conn, clean_cnl_nums, start_3d, end_ts
    )

    summary: dict[int, dict[str, Any]] = {}

    for cnl_num in clean_cnl_nums:
        latest = latest_map.get(cnl_num)
        latest_value = latest["val"] if latest else None

        avg_1h = agg_1h.get(cnl_num, {}).get("avg")

        deviation = None
        deviation_percent = None

        if latest_value is not None and avg_1h not in (None, 0):
            deviation = round_float(float(latest_value) - float(avg_1h))
            deviation_percent = round_float(
                ((float(latest_value) - float(avg_1h)) / float(avg_1h)) * 100
            )

        summary[cnl_num] = {
            "has_history": latest is not None,
            "latest_history_value": round_float(latest_value),
            "latest_history_ts": latest["ts"] if latest else None,

            "avg_1h": avg_1h,
            "avg_24h": agg_24h.get(cnl_num, {}).get("avg"),
            "avg_7d": agg_7d.get(cnl_num, {}).get("avg"),

            "min_24h": agg_24h.get(cnl_num, {}).get("min"),
            "max_24h": agg_24h.get(cnl_num, {}).get("max"),

            "delta_1h": calculate_delta(
                latest_value,
                first_1h.get(cnl_num, {}).get("val"),
            ),
            "delta_24h": calculate_delta(
                latest_value,
                first_24h.get(cnl_num, {}).get("val"),
            ),
            "delta_3d": calculate_delta(
                latest_value,
                first_3d.get(cnl_num, {}).get("val"),
            ),

            "deviation_from_avg_1h": deviation,
            "deviation_percent_from_avg_1h": deviation_percent,
        }

    return summary