from __future__ import annotations

import re

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.analytics.alarm_catalog import load_alarms_config
from app.analytics.categories import (
    CATEGORY_LABELS,
    build_channel_classification,
    get_channel_config,
    is_valid_category,
    load_channels_config,
)
from app.api.routes_alerts import clear_dashboard_snapshot_cache
from app.api.routes_current import get_channel_num, load_metadata_channels
from app.settings.repository import (
    delete_channel_override,
    delete_rule_override,
    get_rule_override_record,
    load_all_channel_override_records,
    load_all_rule_override_records,
    merge_channel_override,
    save_channel_override,
    save_rule_override,
    load_email_notification_settings_record,
    save_email_notification_settings,
)


router = APIRouter(prefix="/api/settings", tags=["settings"])

SEVERITIES = {"normal", "warning", "critical", "unknown"}

TEXT_CHANNEL_FIELDS = {
    "display_name",
    "unit",
    "installation",
    "notes",
}

BOOLEAN_CHANNEL_FIELDS = {
    "zero_flow_enabled",
    "movement_expected",
    "motor_current_expected",
    "allow_negative",
    "dashboard_visible",
}

NUMERIC_CHANNEL_FIELDS = {
    "zero_epsilon",
    "max_delta_1h",
    "max_delta_24h",
    "rapid_change_warning_1h",
    "rapid_change_critical_1h",
    "level_abs_deviation_warning",
    "level_abs_deviation_critical",
}

THRESHOLD_KEYS = {
    "warning_low",
    "critical_low",
    "warning_high",
    "critical_high",
}

NUMERIC_RULE_FIELDS = {
    "zero_epsilon",
    "min_baseline_value",
    "warning_deviation_percent",
    "critical_deviation_percent",
    "warning_below",
    "critical_below",
    "warning_abs_delta",
    "critical_abs_delta",
    "warning_abs_deviation",
    "critical_abs_deviation",
    "warning_min_delta",
    "critical_min_delta",
    "warning_max_delta",
    "critical_max_delta",
}

TEXT_RULE_FIELDS = {
    "reason_template",
    "operator_reason",
    "technical_description",
    "notes",
}

SUPPORTED_CUSTOM_RULE_CONDITIONS = {
    "value_below_threshold": "Τιμή κάτω από όριο",
    "zero_value": "Μηδενική τιμή",
    "negative_value": "Αρνητική τιμή",
    "deviation_below_baseline": "Χαμηλότερη από συνήθη τιμή",
    "deviation_above_baseline": "Υψηλότερη από συνήθη τιμή",
    "absolute_percent_deviation_from_baseline": "Μεγάλη απόκλιση από συνήθη τιμή",
    "rapid_change": "Απότομη μεταβολή",
    "delta_below_min": "Πολύ μικρή μεταβολή",
    "delta_above_max": "Υπερβολική μεταβολή",
}

ALLOWED_RULE_METRICS = {
    "avg_1h",
    "avg_24h",
    "avg_7d",
    "delta_1h",
    "delta_24h",
    "delta_3d",
    "min_24h",
    "max_24h",
}

CUSTOM_RULE_TEXT_FIELDS = {
    "display_name",
    "operator_label",
    "operator_reason",
    "reason_template",
    "technical_description",
    "notes",
    "baseline",
    "baseline_label",
    "delta_field",
}

CUSTOM_RULE_NUMERIC_FIELDS = set(NUMERIC_RULE_FIELDS) | {
    "priority",
    "min_delta_epsilon",
}


def parse_optional_number(value: Any, field_name: str) -> float | None:
    """Parse a nullable numeric setting."""
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise ValueError(f"Το πεδίο {field_name} πρέπει να είναι αριθμός.")

    text = str(value).strip().replace(",", ".")

    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Το πεδίο {field_name} πρέπει να είναι αριθμός.") from exc


def parse_bool(value: Any, field_name: str) -> bool:
    """Parse boolean settings from JSON values."""
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False

    raise ValueError(f"Το πεδίο {field_name} πρέπει να είναι true ή false.")


def clean_text(value: Any) -> str | None:
    """Clean optional text fields."""
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def validate_threshold_order(thresholds: dict[str, Any]) -> None:
    """Validate warning/critical threshold relationships."""
    warning_low = parse_optional_number(thresholds.get("warning_low"), "warning_low")
    critical_low = parse_optional_number(thresholds.get("critical_low"), "critical_low")
    warning_high = parse_optional_number(thresholds.get("warning_high"), "warning_high")
    critical_high = parse_optional_number(thresholds.get("critical_high"), "critical_high")

    if critical_low is not None and warning_low is not None and critical_low > warning_low:
        raise ValueError("Το critical_low πρέπει να είναι μικρότερο ή ίσο από το warning_low.")

    if critical_high is not None and warning_high is not None and critical_high < warning_high:
        raise ValueError("Το critical_high πρέπει να είναι μεγαλύτερο ή ίσο από το warning_high.")


def validate_percent(value: float | None, field_name: str) -> None:
    """Validate percent-like values."""
    if value is None:
        return

    if value < 0 or value > 1000:
        raise ValueError(f"Το {field_name} πρέπει να είναι από 0 έως 1000.")


def clean_thresholds(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract and validate threshold fields."""
    thresholds: dict[str, Any] = {}

    nested = payload.get("thresholds")
    if isinstance(nested, dict):
        for key in THRESHOLD_KEYS:
            if key in nested:
                thresholds[key] = parse_optional_number(nested.get(key), key)

    for key in THRESHOLD_KEYS:
        if key in payload:
            thresholds[key] = parse_optional_number(payload.get(key), key)

    validate_threshold_order(thresholds)

    return thresholds


def clean_rule_overrides(value: Any) -> dict[str, Any]:
    """Validate per-channel rule override dictionary."""
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise ValueError("Το πεδίο rules πρέπει να είναι αντικείμενο JSON.")

    cleaned: dict[str, Any] = {}

    for rule_id, override in value.items():
        if not isinstance(override, dict):
            raise ValueError(f"Το override του κανόνα {rule_id} πρέπει να είναι αντικείμενο JSON.")

        cleaned_rule: dict[str, Any] = {}

        for key, raw_value in override.items():
            if key == "enabled":
                cleaned_rule[key] = parse_bool(raw_value, f"rules.{rule_id}.enabled")
            elif key == "severity":
                severity = str(raw_value or "").strip().lower()
                if severity not in SEVERITIES:
                    raise ValueError(f"Μη αποδεκτό severity στον κανόνα {rule_id}.")
                cleaned_rule[key] = severity
            elif key in NUMERIC_RULE_FIELDS:
                numeric_value = parse_optional_number(raw_value, f"rules.{rule_id}.{key}")
                if "percent" in key:
                    validate_percent(numeric_value, key)
                cleaned_rule[key] = numeric_value
            elif key in TEXT_RULE_FIELDS:
                cleaned_rule[key] = clean_text(raw_value)
            else:
                cleaned_rule[key] = raw_value

        cleaned[str(rule_id)] = cleaned_rule

    return cleaned


def clean_disabled_rules(value: Any) -> list[str]:
    """Validate disabled_rules list."""
    if value is None:
        return []

    if not isinstance(value, list):
        raise ValueError("Το disabled_rules πρέπει να είναι λίστα.")

    return [str(item).strip() for item in value if str(item).strip()]

def clean_rule_id(value: Any, index: int) -> str:
    """Create a safe custom rule id."""
    raw = str(value or "").strip().lower()

    if not raw:
        raw = f"custom_rule_{index + 1}"

    cleaned = re.sub(r"[^a-z0-9_:-]+", "_", raw).strip("_")

    if not cleaned:
        cleaned = f"custom_rule_{index + 1}"

    if not cleaned.startswith("custom_"):
        cleaned = f"custom_{cleaned}"

    return cleaned


def clean_custom_rules(value: Any) -> list[dict[str, Any]]:
    """Validate custom per-channel rules created from the UI."""
    if value is None:
        return []

    if not isinstance(value, list):
        raise ValueError("Το custom_rules πρέπει να είναι λίστα.")

    cleaned_rules: list[dict[str, Any]] = []

    for index, raw_rule in enumerate(value):
        if not isinstance(raw_rule, dict):
            raise ValueError("Κάθε νέος κανόνας πρέπει να είναι JSON object.")

        condition_type = str(raw_rule.get("condition_type") or "").strip()

        if condition_type not in SUPPORTED_CUSTOM_RULE_CONDITIONS:
            raise ValueError(
                "Μη αποδεκτός τύπος νέου κανόνα. "
                "Επιτρεπτές τιμές: "
                + ", ".join(SUPPORTED_CUSTOM_RULE_CONDITIONS.keys())
            )

        rule_id = clean_rule_id(raw_rule.get("rule_id"), index)
        severity = str(raw_rule.get("severity") or "warning").strip().lower()

        if severity not in SEVERITIES:
            raise ValueError(f"Μη αποδεκτό severity στον νέο κανόνα {rule_id}.")

        display_name = clean_text(raw_rule.get("display_name")) or SUPPORTED_CUSTOM_RULE_CONDITIONS[condition_type]
        reason = (
            clean_text(raw_rule.get("operator_reason"))
            or clean_text(raw_rule.get("reason_template"))
            or f"Ενεργοποιήθηκε ο έλεγχος: {display_name}."
        )

        cleaned: dict[str, Any] = {
            "rule_id": rule_id,
            "enabled": parse_bool(raw_rule.get("enabled", True), f"custom_rules.{rule_id}.enabled"),
            "condition_type": condition_type,
            "severity": severity,
            "display_name": display_name,
            "operator_label": display_name,
            "operator_reason": reason,
            "reason_template": reason,
            "priority": 90,
        }

        for key in CUSTOM_RULE_TEXT_FIELDS:
            if key not in raw_rule:
                continue

            text_value = clean_text(raw_rule.get(key))

            if key in {"baseline", "delta_field"}:
                if text_value and text_value not in ALLOWED_RULE_METRICS:
                    raise ValueError(
                        f"Το {key} στον νέο κανόνα {rule_id} πρέπει να είναι ένα από: "
                        + ", ".join(sorted(ALLOWED_RULE_METRICS))
                    )

            if text_value is not None:
                cleaned[key] = text_value

        for key in CUSTOM_RULE_NUMERIC_FIELDS:
            if key not in raw_rule:
                continue

            numeric_value = parse_optional_number(raw_rule.get(key), f"custom_rules.{rule_id}.{key}")

            if "percent" in key:
                validate_percent(numeric_value, key)

            if key == "priority" and numeric_value is not None:
                if numeric_value < 1 or numeric_value > 999:
                    raise ValueError("Το priority πρέπει να είναι από 1 έως 999.")
                cleaned[key] = int(numeric_value)
            else:
                cleaned[key] = numeric_value

        if condition_type in {
            "deviation_below_baseline",
            "deviation_above_baseline",
            "absolute_percent_deviation_from_baseline",
        }:
            cleaned.setdefault("baseline", "avg_24h")
            cleaned.setdefault("baseline_label", "Μ.Ο. 24ώρου")

        if condition_type in {
            "rapid_change",
            "delta_below_min",
            "delta_above_max",
        }:
            cleaned.setdefault("delta_field", "delta_1h")

        if cleaned.get("enabled", True):
            if condition_type == "value_below_threshold":
                if cleaned.get("warning_below") is None and cleaned.get("critical_below") is None:
                    raise ValueError(
                        f"Ο νέος έλεγχος {rule_id} χρειάζεται τουλάχιστον ένα όριο."
                    )

            if condition_type == "zero_value":
                if cleaned.get("zero_epsilon") is None:
                    raise ValueError(
                        f"Ο νέος έλεγχος {rule_id} χρειάζεται τιμή που θεωρείται μηδενική."
                    )

            if condition_type == "negative_value":
                if cleaned.get("critical_below") is None:
                    cleaned["critical_below"] = 0.0

            if condition_type in {
                "deviation_below_baseline",
                "deviation_above_baseline",
                "absolute_percent_deviation_from_baseline",
            }:
                if (
                    cleaned.get("warning_deviation_percent") is None
                    and cleaned.get("critical_deviation_percent") is None
                ):
                    raise ValueError(
                        f"Ο νέος έλεγχος {rule_id} χρειάζεται ποσοστό απόκλισης."
                    )

            if condition_type == "rapid_change":
                if cleaned.get("warning_abs_delta") is None and cleaned.get("critical_abs_delta") is None:
                    raise ValueError(
                        f"Ο νέος έλεγχος {rule_id} χρειάζεται όριο μεταβολής."
                    )

            if condition_type == "delta_below_min":
                if cleaned.get("warning_min_delta") is None and cleaned.get("critical_min_delta") is None:
                    raise ValueError(
                        f"Ο νέος έλεγχος {rule_id} χρειάζεται όριο ελάχιστης μεταβολής."
                    )

            if condition_type == "delta_above_max":
                if cleaned.get("warning_max_delta") is None:
                    raise ValueError(
                        f"Ο νέος έλεγχος {rule_id} χρειάζεται τιμή υπερβολικής μεταβολής."
                    )    
        cleaned_rules.append(cleaned)

    return cleaned_rules


def clean_channel_settings_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Clean and validate a channel settings override payload."""
    if not isinstance(payload, dict):
        raise ValueError("Το σώμα του request πρέπει να είναι JSON object.")

    cleaned: dict[str, Any] = {}

    for field in TEXT_CHANNEL_FIELDS:
        if field in payload:
            cleaned[field] = clean_text(payload.get(field))

    if "category" in payload:
        category = str(payload.get("category") or "").strip()
        if not is_valid_category(category):
            raise ValueError(
                "Μη αποδεκτή κατηγορία. Επιτρεπτές τιμές: "
                + ", ".join(CATEGORY_LABELS.keys())
            )
        cleaned["category"] = category

    for field in BOOLEAN_CHANNEL_FIELDS:
        if field in payload:
            cleaned[field] = parse_bool(payload.get(field), field)

    for field in NUMERIC_CHANNEL_FIELDS:
        if field in payload:
            cleaned[field] = parse_optional_number(payload.get(field), field)

    thresholds = clean_thresholds(payload)
    if thresholds:
        cleaned["thresholds"] = thresholds

    if "disabled_rules" in payload:
        cleaned["disabled_rules"] = clean_disabled_rules(payload.get("disabled_rules"))

    if "rules" in payload:
        cleaned["rules"] = clean_rule_overrides(payload.get("rules"))

    if "custom_rules" in payload:
        cleaned["custom_rules"] = clean_custom_rules(payload.get("custom_rules"))

    return cleaned


def flatten_catalog_rules(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten category_rules into a single rule list."""
    category_rules = catalog.get("category_rules", {})
    if not isinstance(category_rules, dict):
        return []

    result: list[dict[str, Any]] = []

    for category, rules in category_rules.items():
        if not isinstance(rules, list):
            continue

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            item = dict(rule)
            item.setdefault("category", category)
            result.append(item)

    return result


def get_rule_by_id(catalog: dict[str, Any], rule_id: str) -> dict[str, Any] | None:
    """Find one rule inside an alarm catalog."""
    for rule in flatten_catalog_rules(catalog):
        if str(rule.get("rule_id") or "") == rule_id:
            return rule

    return None


def clean_global_rule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Clean and validate a global rule override payload."""
    if not isinstance(payload, dict):
        raise ValueError("Το σώμα του request πρέπει να είναι JSON object.")

    cleaned: dict[str, Any] = {}

    if "enabled" in payload:
        cleaned["enabled"] = parse_bool(payload.get("enabled"), "enabled")

    if "severity" in payload:
        severity = str(payload.get("severity") or "").strip().lower()
        if severity not in SEVERITIES:
            raise ValueError("Μη αποδεκτό severity.")
        cleaned["severity"] = severity

    for field in NUMERIC_RULE_FIELDS:
        if field in payload:
            numeric_value = parse_optional_number(payload.get(field), field)
            if "percent" in field:
                validate_percent(numeric_value, field)
            cleaned[field] = numeric_value

    for field in TEXT_RULE_FIELDS:
        if field in payload:
            cleaned[field] = clean_text(payload.get(field))

    return cleaned


def build_channel_settings_row(
    channel: dict[str, Any],
    *,
    default_config: dict[str, Any],
    effective_config: dict[str, Any],
    override_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build one channel row for settings UI."""
    cnl_num = get_channel_num(channel)
    if cnl_num is None:
        raise ValueError("Channel without cnl_num.")

    cnl_key = str(cnl_num)
    default_channel_config = get_channel_config(cnl_num, config=default_config)
    effective_channel_config = get_channel_config(cnl_num, config=effective_config)
    override_record = override_records.get(cnl_key)

    classification = build_channel_classification(channel, config=effective_config)

    return {
        "cnl_num": cnl_num,
        "name": channel.get("name"),
        "tag_code": channel.get("tag_code"),
        "device_name": channel.get("device_name"),
        "comm_line_name": channel.get("comm_line_name"),
        "category": classification["category"],
        "category_label": classification["category_label"],
        "display_name": classification["display_name"] or channel.get("name"),
        "unit": classification["unit"],
        "installation": classification["installation"],
        "dashboard_visible": classification.get("dashboard_visible", True),
        "default_config": default_channel_config,
        "ui_override": override_record.get("settings") if override_record else {},
        "ui_override_updated_at": override_record.get("updated_at") if override_record else None,
        "effective_config": effective_channel_config,
        "has_ui_override": override_record is not None,
    }

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean_email_list(value: Any) -> list[str]:
    """Clean and validate email recipients."""
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = re.split(r"[\n,;]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raise ValueError("Η λίστα email πρέπει να είναι λίστα ή κείμενο.")

    emails: list[str] = []

    for item in raw_items:
        email = str(item or "").strip().lower()
        if not email:
            continue

        if not EMAIL_PATTERN.match(email):
            raise ValueError(f"Μη έγκυρη διεύθυνση email: {email}")

        if email not in emails:
            emails.append(email)

    return emails


def clean_email_notification_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Clean email notification settings payload."""
    if not isinstance(payload, dict):
        raise ValueError("Το σώμα του request πρέπει να είναι JSON object.")

    cleaned: dict[str, Any] = {}

    if "enabled" in payload:
        cleaned["enabled"] = parse_bool(payload.get("enabled"), "enabled")

    if "recipients" in payload:
        cleaned["recipients"] = clean_email_list(payload.get("recipients"))

    cleaned["only_static_critical_thresholds"] = True

    return cleaned


@router.get("/email-notifications")
async def get_email_notification_settings() -> dict[str, Any]:
    """Return email notification settings."""
    record = load_email_notification_settings_record()

    return {
        "ok": True,
        "settings": record["settings"],
        "updated_at": record["updated_at"],
    }


@router.put("/email-notifications")
async def put_email_notification_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """Save email notification settings."""
    try:
        cleaned = clean_email_notification_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saved = save_email_notification_settings(cleaned)

    return {
        "ok": True,
        "message": "Οι ρυθμίσεις email αποθηκεύτηκαν.",
        "settings": saved["settings"],
        "updated_at": saved["updated_at"],
    }

@router.get("/channels")
async def get_settings_channels(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    only_overridden: bool = Query(default=False),
) -> dict[str, Any]:
    """Return channels with default/effective/UI override settings."""
    default_config = load_channels_config(include_ui_overrides=False)
    effective_config = load_channels_config(include_ui_overrides=True)
    override_records = load_all_channel_override_records()

    metadata_channels = load_metadata_channels(active_only=True)

    rows = [
        build_channel_settings_row(
            channel,
            default_config=default_config,
            effective_config=effective_config,
            override_records=override_records,
        )
        for channel in metadata_channels
    ]

    if search:
        term = search.strip().lower()
        rows = [
            row for row in rows
            if term in " ".join(
                str(row.get(key) or "").lower()
                for key in (
                    "cnl_num",
                    "name",
                    "display_name",
                    "tag_code",
                    "device_name",
                    "comm_line_name",
                    "installation",
                    "category_label",
                )
            )
        ]

    if category:
        rows = [row for row in rows if row.get("category") == category]

    if only_overridden:
        rows = [row for row in rows if row.get("has_ui_override")]

    return {
        "ok": True,
        "count": len(rows),
        "items": rows,
        "allowed_categories": [
            {"category": key, "label": label}
            for key, label in CATEGORY_LABELS.items()
        ],
    }


@router.get("/channels/{cnl_num}")
async def get_settings_channel(cnl_num: int) -> dict[str, Any]:
    """Return one channel settings row."""
    default_config = load_channels_config(include_ui_overrides=False)
    effective_config = load_channels_config(include_ui_overrides=True)
    override_records = load_all_channel_override_records()

    metadata_channels = load_metadata_channels(active_only=True)
    channel = next(
        (
            item for item in metadata_channels
            if get_channel_num(item) == cnl_num
        ),
        None,
    )

    if channel is None:
        raise HTTPException(status_code=404, detail="Δεν βρέθηκε ενεργό κανάλι με αυτό το cnl_num.")

    return {
        "ok": True,
        "item": build_channel_settings_row(
            channel,
            default_config=default_config,
            effective_config=effective_config,
            override_records=override_records,
        ),
    }


@router.put("/channels/{cnl_num}")
async def put_settings_channel(cnl_num: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Save one channel UI override."""
    try:
        cleaned = clean_channel_settings_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saved = save_channel_override(cnl_num, cleaned)
    clear_dashboard_snapshot_cache()

    return {
        "ok": True,
        "message": "Οι ρυθμίσεις καναλιού αποθηκεύτηκαν στο local dashboard settings DB.",
        "saved": saved,
    }


@router.delete("/channels/{cnl_num}")
async def delete_settings_channel(cnl_num: int) -> dict[str, Any]:
    """Delete one channel UI override and return to default config."""
    deleted = delete_channel_override(cnl_num)
    clear_dashboard_snapshot_cache()

    return {
        "ok": True,
        "deleted": deleted,
        "message": "Το UI override του καναλιού αφαιρέθηκε. Θα χρησιμοποιείται ξανά το default config.",
    }


@router.put("/categories/{category}/visibility")
async def put_settings_category_visibility(
    category: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Show or hide all active channels of a category in the dashboard."""
    if not is_valid_category(category):
        raise HTTPException(
            status_code=400,
            detail="Μη αποδεκτή κατηγορία. Επιτρεπτές τιμές: " + ", ".join(CATEGORY_LABELS.keys()),
        )

    try:
        visible = parse_bool(payload.get("visible"), "visible")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    effective_config = load_channels_config(include_ui_overrides=True)
    metadata_channels = load_metadata_channels(active_only=True)
    updated: list[int] = []

    for channel in metadata_channels:
        cnl_num = get_channel_num(channel)
        if cnl_num is None:
            continue

        classification = build_channel_classification(channel, config=effective_config)
        if classification.get("category") != category:
            continue

        merge_channel_override(cnl_num, {"dashboard_visible": visible})
        updated.append(cnl_num)

    clear_dashboard_snapshot_cache()

    return {
        "ok": True,
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, category),
        "visible": visible,
        "updated_count": len(updated),
        "updated_cnl_nums": updated,
        "message": "Η εμφάνιση της κατηγορίας ενημερώθηκε για το dashboard.",
    }

@router.get("/rules")
async def get_settings_rules(
    category: str | None = Query(default=None),
    only_overridden: bool = Query(default=False),
) -> dict[str, Any]:
    """Return rule catalog with default/effective/UI override data."""
    default_catalog = load_alarms_config(include_ui_overrides=False)
    effective_catalog = load_alarms_config(include_ui_overrides=True)
    override_records = load_all_rule_override_records()

    default_rules_by_id = {
        str(rule.get("rule_id")): rule
        for rule in flatten_catalog_rules(default_catalog)
        if rule.get("rule_id")
    }

    rows: list[dict[str, Any]] = []

    for effective_rule in flatten_catalog_rules(effective_catalog):
        rule_id = str(effective_rule.get("rule_id") or "")
        if not rule_id:
            continue

        row_category = effective_rule.get("category")
        override_record = override_records.get(rule_id)

        row = {
            "rule_id": rule_id,
            "category": row_category,
            "enabled": effective_rule.get("enabled", True),
            "condition_type": effective_rule.get("condition_type"),
            "severity": effective_rule.get("severity"),
            "priority": effective_rule.get("priority"),
            "reason_template": effective_rule.get("reason_template"),
            "operator_reason": effective_rule.get("operator_reason"),
            "technical_description": effective_rule.get("technical_description"),
            "notes": effective_rule.get("notes"),
            "default_rule": default_rules_by_id.get(rule_id, {}),
            "ui_override": override_record.get("settings") if override_record else {},
            "ui_override_updated_at": override_record.get("updated_at") if override_record else None,
            "effective_rule": effective_rule,
            "has_ui_override": override_record is not None,
        }

        rows.append(row)

    if category:
        rows = [row for row in rows if row.get("category") in {category, "all"}]

    if only_overridden:
        rows = [row for row in rows if row.get("has_ui_override")]

    return {
        "ok": True,
        "count": len(rows),
        "items": rows,
    }


@router.get("/rules/{rule_id}")
async def get_settings_rule(rule_id: str) -> dict[str, Any]:
    """Return one global rule settings row."""
    default_catalog = load_alarms_config(include_ui_overrides=False)
    effective_catalog = load_alarms_config(include_ui_overrides=True)

    default_rule = get_rule_by_id(default_catalog, rule_id)
    effective_rule = get_rule_by_id(effective_catalog, rule_id)

    if effective_rule is None:
        raise HTTPException(status_code=404, detail="Δεν βρέθηκε κανόνας με αυτό το rule_id.")

    override_record = get_rule_override_record(rule_id)

    return {
        "ok": True,
        "item": {
            "rule_id": rule_id,
            "category": effective_rule.get("category"),
            "default_rule": default_rule or {},
            "ui_override": override_record.get("settings") if override_record else {},
            "ui_override_updated_at": override_record.get("updated_at") if override_record else None,
            "effective_rule": effective_rule,
            "has_ui_override": override_record is not None,
        },
    }


@router.put("/rules/{rule_id}")
async def put_settings_rule(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Save one global rule UI override."""
    default_catalog = load_alarms_config(include_ui_overrides=False)

    if get_rule_by_id(default_catalog, rule_id) is None:
        raise HTTPException(status_code=404, detail="Δεν βρέθηκε κανόνας με αυτό το rule_id.")

    try:
        cleaned = clean_global_rule_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saved = save_rule_override(rule_id, cleaned)
    clear_dashboard_snapshot_cache()

    return {
        "ok": True,
        "message": "Οι ρυθμίσεις κανόνα αποθηκεύτηκαν στο local dashboard settings DB.",
        "saved": saved,
    }


@router.delete("/rules/{rule_id}")
async def delete_settings_rule(rule_id: str) -> dict[str, Any]:
    """Delete one global rule UI override and return to default catalog."""
    deleted = delete_rule_override(rule_id)
    clear_dashboard_snapshot_cache()

    return {
        "ok": True,
        "deleted": deleted,
        "message": "Το UI override του κανόνα αφαιρέθηκε. Θα χρησιμοποιείται ξανά το default alarm catalog.",
    }


@router.post("/reload")
async def reload_settings() -> dict[str, Any]:
    """Clear dashboard cache so settings are applied on the next evaluation."""
    clear_dashboard_snapshot_cache()

    return {
        "ok": True,
        "message": "Καθαρίστηκε η cache του dashboard. Οι ρυθμίσεις θα εφαρμοστούν στον επόμενο υπολογισμό alerts/overview.",
    }