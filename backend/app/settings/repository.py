from __future__ import annotations

import copy
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
SETTINGS_DB_PATH = BASE_DIR / "data" / "dashboard_settings.sqlite3"


def utc_now_iso() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def get_settings_db_path() -> Path:
    """Return the local SQLite settings database path."""
    SETTINGS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return SETTINGS_DB_PATH


def open_settings_db() -> sqlite3.Connection:
    """Open the local dashboard settings database."""
    conn = sqlite3.connect(get_settings_db_path())
    conn.row_factory = sqlite3.Row
    ensure_settings_schema(conn)
    return conn


def ensure_settings_schema(conn: sqlite3.Connection) -> None:
    """Create settings tables if they do not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS channel_settings_overrides (
            cnl_num INTEGER PRIMARY KEY,
            settings_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_settings_overrides (
            rule_id TEXT PRIMARY KEY,
            settings_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_notification_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            settings_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_notification_state (
            notification_key TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.commit()


def json_dumps(data: dict[str, Any]) -> str:
    """Serialize settings as stable UTF-8 JSON text."""
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def json_loads(value: str | None) -> dict[str, Any]:
    """Parse settings JSON safely."""
    if not value:
        return {}

    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


def deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Merge two dictionaries recursively.

    Values from override win over base.
    """
    result = copy.deepcopy(base)

    for key, value in override.items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
        ):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result


def load_all_channel_override_records() -> dict[str, dict[str, Any]]:
    """Return all channel override records from SQLite."""
    with open_settings_db() as conn:
        rows = conn.execute(
            """
            SELECT cnl_num, settings_json, updated_at
            FROM channel_settings_overrides
            ORDER BY cnl_num
            """
        ).fetchall()

    result: dict[str, dict[str, Any]] = {}

    for row in rows:
        result[str(row["cnl_num"])] = {
            "settings": json_loads(row["settings_json"]),
            "updated_at": row["updated_at"],
        }

    return result

def get_channel_override_record(cnl_num: int | str) -> dict[str, Any] | None:
    """Return one channel override record."""
    with open_settings_db() as conn:
        row = conn.execute(
            """
            SELECT cnl_num, settings_json, updated_at
            FROM channel_settings_overrides
            WHERE cnl_num = ?
            """,
            (int(cnl_num),),
        ).fetchone()

    if row is None:
        return None

    return {
        "cnl_num": int(row["cnl_num"]),
        "settings": json_loads(row["settings_json"]),
        "updated_at": row["updated_at"],
    }


def merge_channel_override(cnl_num: int | str, partial_settings: dict[str, Any]) -> dict[str, Any]:
    """Merge partial settings into an existing channel override."""
    current_record = get_channel_override_record(cnl_num)
    current_settings = (
        current_record.get("settings", {})
        if isinstance(current_record, dict)
        else {}
    )

    if not isinstance(current_settings, dict):
        current_settings = {}

    merged_settings = deep_merge_dicts(current_settings, partial_settings)
    return save_channel_override(cnl_num, merged_settings)


def save_channel_override(cnl_num: int | str, settings: dict[str, Any]) -> dict[str, Any]:
    """Insert or update one channel override."""
    updated_at = utc_now_iso()

    with open_settings_db() as conn:
        conn.execute(
            """
            INSERT INTO channel_settings_overrides (cnl_num, settings_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cnl_num) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_at = excluded.updated_at
            """,
            (int(cnl_num), json_dumps(settings), updated_at),
        )
        conn.commit()

    return {
        "cnl_num": int(cnl_num),
        "settings": settings,
        "updated_at": updated_at,
    }


def delete_channel_override(cnl_num: int | str) -> bool:
    """Delete one channel override. Returns true if a row was removed."""
    with open_settings_db() as conn:
        cursor = conn.execute(
            "DELETE FROM channel_settings_overrides WHERE cnl_num = ?",
            (int(cnl_num),),
        )
        conn.commit()

    return cursor.rowcount > 0


def load_all_rule_override_records() -> dict[str, dict[str, Any]]:
    """Return all global rule override records from SQLite."""
    with open_settings_db() as conn:
        rows = conn.execute(
            """
            SELECT rule_id, settings_json, updated_at
            FROM rule_settings_overrides
            ORDER BY rule_id
            """
        ).fetchall()

    result: dict[str, dict[str, Any]] = {}

    for row in rows:
        result[str(row["rule_id"])] = {
            "settings": json_loads(row["settings_json"]),
            "updated_at": row["updated_at"],
        }

    return result


def load_all_rule_setting_overrides() -> dict[str, dict[str, Any]]:
    """Return all global rule override settings, without metadata."""
    records = load_all_rule_override_records()
    return {
        rule_id: record["settings"]
        for rule_id, record in records.items()
        if isinstance(record.get("settings"), dict)
    }


def get_rule_override_record(rule_id: str) -> dict[str, Any] | None:
    """Return one global rule override record."""
    with open_settings_db() as conn:
        row = conn.execute(
            """
            SELECT rule_id, settings_json, updated_at
            FROM rule_settings_overrides
            WHERE rule_id = ?
            """,
            (rule_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "rule_id": str(row["rule_id"]),
        "settings": json_loads(row["settings_json"]),
        "updated_at": row["updated_at"],
    }


def save_rule_override(rule_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    """Insert or update one global rule override."""
    updated_at = utc_now_iso()

    with open_settings_db() as conn:
        conn.execute(
            """
            INSERT INTO rule_settings_overrides (rule_id, settings_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(rule_id) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_at = excluded.updated_at
            """,
            (rule_id, json_dumps(settings), updated_at),
        )
        conn.commit()

    return {
        "rule_id": rule_id,
        "settings": settings,
        "updated_at": updated_at,
    }


def delete_rule_override(rule_id: str) -> bool:
    """Delete one global rule override. Returns true if a row was removed."""
    with open_settings_db() as conn:
        cursor = conn.execute(
            "DELETE FROM rule_settings_overrides WHERE rule_id = ?",
            (rule_id,),
        )
        conn.commit()

    return cursor.rowcount > 0


def apply_channel_overrides_to_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Apply SQLite channel overrides on top of channels_config.json.

    This keeps JSON as seed/default config and uses SQLite for runtime UI changes.
    """
    result = copy.deepcopy(config)

    channels = result.get("channels")
    if not isinstance(channels, dict):
        channels = {}
        result["channels"] = channels

    override_records = load_all_channel_override_records()

    for cnl_num, record in override_records.items():
        override_settings = record.get("settings", {})
        if not isinstance(override_settings, dict):
            continue

        default_settings = channels.get(str(cnl_num), {})
        if not isinstance(default_settings, dict):
            default_settings = {}

        merged = deep_merge_dicts(default_settings, override_settings)
        merged["_has_ui_override"] = True
        merged["_ui_override_updated_at"] = record.get("updated_at")

        channels[str(cnl_num)] = merged

    return result


def apply_rule_overrides_to_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    """
    Apply SQLite global rule overrides on top of alarms_config.json.

    Per-channel rule overrides still go through channel config.
    """
    result = copy.deepcopy(catalog)
    overrides = load_all_rule_setting_overrides()

    if not overrides:
        return result

    category_rules = result.get("category_rules", {})
    if not isinstance(category_rules, dict):
        return result

    for rules in category_rules.values():
        if not isinstance(rules, list):
            continue

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            rule_id = str(rule.get("rule_id") or "").strip()
            override = overrides.get(rule_id)

            if isinstance(override, dict):
                rule.update(override)
                rule["_has_ui_override"] = True

    return result

DEFAULT_EMAIL_NOTIFICATION_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "recipients": [],
    "only_static_critical_thresholds": True,
}


def load_email_notification_settings_record() -> dict[str, Any]:
    """Return email notification settings from SQLite."""
    with open_settings_db() as conn:
        row = conn.execute(
            """
            SELECT settings_json, updated_at
            FROM email_notification_settings
            WHERE id = 1
            """
        ).fetchone()

    if row is None:
        return {
            "settings": dict(DEFAULT_EMAIL_NOTIFICATION_SETTINGS),
            "updated_at": None,
        }

    settings = deep_merge_dicts(
        DEFAULT_EMAIL_NOTIFICATION_SETTINGS,
        json_loads(row["settings_json"]),
    )

    return {
        "settings": settings,
        "updated_at": row["updated_at"],
    }


def save_email_notification_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Save email notification settings to SQLite."""
    updated_at = utc_now_iso()

    merged_settings = deep_merge_dicts(
        DEFAULT_EMAIL_NOTIFICATION_SETTINGS,
        settings,
    )

    with open_settings_db() as conn:
        conn.execute(
            """
            INSERT INTO email_notification_settings (id, settings_json, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_at = excluded.updated_at
            """,
            (json_dumps(merged_settings), updated_at),
        )
        conn.commit()

    return {
        "settings": merged_settings,
        "updated_at": updated_at,
    }

def load_active_email_notification_state_records() -> dict[str, dict[str, Any]]:
    """Return active email notification states."""
    with open_settings_db() as conn:
        rows = conn.execute(
            """
            SELECT notification_key, state_json, active, updated_at
            FROM email_notification_state
            WHERE active = 1
            ORDER BY notification_key
            """
        ).fetchall()

    result: dict[str, dict[str, Any]] = {}

    for row in rows:
        result[str(row["notification_key"])] = {
            "state": json_loads(row["state_json"]),
            "active": bool(row["active"]),
            "updated_at": row["updated_at"],
        }

    return result


def save_email_notification_state(
    notification_key: str,
    state: dict[str, Any],
    *,
    active: bool,
) -> dict[str, Any]:
    """Insert or update one email notification state."""
    updated_at = utc_now_iso()
    state_to_save = dict(state)
    state_to_save["active"] = active

    with open_settings_db() as conn:
        conn.execute(
            """
            INSERT INTO email_notification_state (
                notification_key,
                state_json,
                active,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(notification_key) DO UPDATE SET
                state_json = excluded.state_json,
                active = excluded.active,
                updated_at = excluded.updated_at
            """,
            (
                notification_key,
                json_dumps(state_to_save),
                1 if active else 0,
                updated_at,
            ),
        )
        conn.commit()

    return {
        "notification_key": notification_key,
        "state": state_to_save,
        "active": active,
        "updated_at": updated_at,
    }