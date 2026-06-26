from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ALARMS_CONFIG_PATH = BASE_DIR / "config" / "alarms_config.json"


def load_alarms_config(
    config_path: str | Path = DEFAULT_ALARMS_CONFIG_PATH,
    *,
    include_ui_overrides: bool = True,
) -> dict[str, Any]:
    """Load the alarm/rule catalog from JSON and optional UI overrides."""
    path = Path(config_path)

    if not path.exists():
        data = {
            "version": 1,
            "enabled": True,
            "category_rules": {},
            "channel_overrides": {},
        }
    else:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

    if not isinstance(data, dict):
        data = {
            "version": 1,
            "enabled": True,
            "category_rules": {},
            "channel_overrides": {},
        }

    category_rules = data.get("category_rules", {})
    if not isinstance(category_rules, dict):
        data["category_rules"] = {}

    channel_overrides = data.get("channel_overrides", {})
    if not isinstance(channel_overrides, dict):
        data["channel_overrides"] = {}
    else:
        data["channel_overrides"] = {
            str(cnl_num): value
            for cnl_num, value in channel_overrides.items()
            if isinstance(value, dict)
        }

    if include_ui_overrides:
        from app.settings.repository import apply_rule_overrides_to_catalog

        data = apply_rule_overrides_to_catalog(data)

    return data


def get_catalog_rules_for_category(
    category: str | None,
    catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return normalized catalog rules for one channel category."""
    data = catalog if catalog is not None else load_alarms_config()
    category_key = category or "unknown"
    category_rules = data.get("category_rules", {})

    rules: list[dict[str, Any]] = []

    for key in ("all", category_key):
        raw_rules = category_rules.get(key, []) if isinstance(category_rules, dict) else []
        if not isinstance(raw_rules, list):
            continue

        for raw_rule in raw_rules:
            if not isinstance(raw_rule, dict):
                continue

            rule = dict(raw_rule)
            rule.setdefault("category", key)
            rules.append(rule)

    return rules


def get_catalog_channel_override(
    cnl_num: int | str | None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return alarm catalog overrides for one channel."""
    if cnl_num is None:
        return {}

    data = catalog if catalog is not None else load_alarms_config()
    overrides = data.get("channel_overrides", {})

    if not isinstance(overrides, dict):
        return {}

    override = overrides.get(str(cnl_num), {})
    return override if isinstance(override, dict) else {}