from __future__ import annotations

from math import isfinite
from typing import Any

from app.analytics.categories import (
    get_category_label,
    get_channel_config,
    load_channels_config,
)


SEVERITY_LABELS: dict[str, str] = {
    "normal": "Κανονικό",
    "warning": "Προειδοποίηση",
    "critical": "Κρίσιμο",
    "unknown": "Άγνωστο",
}

SEVERITY_PRIORITY: dict[str, int] = {
    "critical": 0,
    "warning": 1,
    "unknown": 2,
    "normal": 3,
}

VALID_SCADA_STATUS_IDS = {1, 2, 13, 21}

INVALID_SCADA_STATUS_TEXT_TERMS = [
    "undefined",
    "invalid",
    "error",
    "formula error",
    "unreliable",
    "no data",
    "μη έγκυ",
    "σφάλ",
]

DEFAULT_INVALID_SEVERITY_BY_CATEGORY: dict[str, str] = {
    "flow": "warning",
    "cumulative_flow": "warning",
    "level": "critical",
    "quality": "warning",
    "motor_current": "warning",
    "pressure": "warning",
    "unknown": "warning",
}


def normalize_severity(value: Any, default: str = "warning") -> str:
    """Normalize severity to a supported internal value."""
    text = str(value or "").strip().lower()

    if text in SEVERITY_LABELS:
        return text

    return default


def get_severity_label(severity: str) -> str:
    """Return Greek label for severity."""
    return SEVERITY_LABELS.get(severity, SEVERITY_LABELS["unknown"])


def parse_number(value: Any) -> float | None:
    """Parse a numeric current value safely."""
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int | float):
        numeric_value = float(value)
        return numeric_value if isfinite(numeric_value) else None

    text = str(value).strip().replace(",", ".")

    if not text:
        return None

    try:
        numeric_value = float(text)
    except ValueError:
        return None

    return numeric_value if isfinite(numeric_value) else None


def parse_optional_number(value: Any) -> float | None:
    """Parse optional config threshold values."""
    if value is None or value == "":
        return None

    return parse_number(value)


def get_threshold(channel_config: dict[str, Any], key: str) -> float | None:
    """Read a threshold either from flat config or nested thresholds."""
    thresholds = channel_config.get("thresholds", {})

    if isinstance(thresholds, dict) and key in thresholds:
        return parse_optional_number(thresholds.get(key))

    return parse_optional_number(channel_config.get(key))


def is_scada_status_valid(channel: dict[str, Any]) -> bool:
    """Check if SCADA says that the channel value is valid enough to evaluate."""
    status = channel.get("scada_status")

    try:
        status_id = int(status)
    except (TypeError, ValueError):
        status_id = None

    status_text = (
        f"{channel.get('scada_status_text') or ''} "
        f"{channel.get('scada_status_description') or ''}"
    ).lower()

    if status_id in VALID_SCADA_STATUS_IDS:
        return True

    if any(term in status_text for term in INVALID_SCADA_STATUS_TEXT_TERMS):
        return False

    if status_id is None:
        return False

    return True


def is_scada_status_normal(channel: dict[str, Any]) -> bool:
    """Check if SCADA status is normal/valid for summary purposes."""
    try:
        status_id = int(channel.get("scada_status"))
    except (TypeError, ValueError):
        return False

    return status_id in VALID_SCADA_STATUS_IDS


def make_alert(
    *,
    channel: dict[str, Any],
    severity: str,
    reason: str,
    rule_id: str,
    rule_type: str,
) -> dict[str, Any]:
    """Create a normalized alert/evaluation object."""
    cnl_num = channel.get("cnl_num")
    category = channel.get("category") or "unknown"

    return {
        "alert_id": f"{rule_id}:{cnl_num}",
        "cnl_num": cnl_num,
        "channel_name": channel.get("display_name") or channel.get("name"),
        "display_name": channel.get("display_name") or channel.get("name"),
        "category": category,
        "category_label": channel.get("category_label") or get_category_label(category),
        "severity": severity,
        "severity_label": get_severity_label(severity),
        "current_value": channel.get("current_value"),
        "unit": channel.get("unit"),
        "reason": reason,
        "scada_status": channel.get("scada_status"),
        "scada_status_text": channel.get("scada_status_text"),
        "fetched_at": channel.get("fetched_at"),
        "last_update": channel.get("last_update"),
        "rule_id": rule_id,
        "rule_type": rule_type,
    }


def get_invalid_value_severity(
    category: str,
    channel_config: dict[str, Any],
) -> str:
    """Get invalid value severity from config or category defaults."""
    configured = channel_config.get("invalid_value_severity")

    if configured:
        return normalize_severity(configured)

    default = DEFAULT_INVALID_SEVERITY_BY_CATEGORY.get(category, "warning")
    return normalize_severity(default)


def build_invalid_value_alert(
    channel: dict[str, Any],
    channel_config: dict[str, Any],
    numeric_value: float | None,
) -> dict[str, Any] | None:
    """Create invalid/undefined value alert when needed."""
    category = channel.get("category") or "unknown"
    severity = get_invalid_value_severity(category, channel_config)

    if not is_scada_status_valid(channel):
        return make_alert(
            channel=channel,
            severity=severity,
            reason="Η τιμή του καναλιού δεν είναι έγκυρη σύμφωνα με το SCADA.",
            rule_id="invalid_scada_value",
            rule_type="invalid_value",
        )

    if numeric_value is None:
        return make_alert(
            channel=channel,
            severity=severity,
            reason="Η τιμή του καναλιού δεν είναι αριθμητική και δεν μπορεί να αξιολογηθεί.",
            rule_id="non_numeric_value",
            rule_type="invalid_value",
        )

    return None


def threshold_reason(category: str, bound: str, severity: str) -> str:
    """Build Greek reason text for threshold violations."""
    is_low = bound == "low"
    is_critical = severity == "critical"

    if category == "level":
        if is_low and is_critical:
            return "Η στάθμη είναι χαμηλότερη από το κρίσιμο όριο."
        if is_low:
            return "Η στάθμη είναι κάτω από το όριο προειδοποίησης."
        if is_critical:
            return "Η στάθμη είναι υψηλότερη από το κρίσιμο όριο."
        return "Η στάθμη είναι πάνω από το όριο προειδοποίησης."

    if is_low and is_critical:
        return "Η τιμή είναι κάτω από το κρίσιμο όριο."
    if is_low:
        return "Η τιμή είναι κάτω από το όριο προειδοποίησης."
    if is_critical:
        return "Η τιμή είναι πάνω από το κρίσιμο όριο."

    return "Η τιμή είναι πάνω από το όριο προειδοποίησης."


def build_threshold_alerts(
    channel: dict[str, Any],
    channel_config: dict[str, Any],
    numeric_value: float,
) -> list[dict[str, Any]]:
    """Evaluate static warning/critical thresholds."""
    category = channel.get("category") or "unknown"
    rule_type = "level_out_of_bounds" if category == "level" else "static_threshold"

    critical_low = get_threshold(channel_config, "critical_low")
    warning_low = get_threshold(channel_config, "warning_low")
    warning_high = get_threshold(channel_config, "warning_high")
    critical_high = get_threshold(channel_config, "critical_high")

    alerts: list[dict[str, Any]] = []

    if critical_low is not None and numeric_value < critical_low:
        alerts.append(
            make_alert(
                channel=channel,
                severity="critical",
                reason=threshold_reason(category, "low", "critical"),
                rule_id="threshold_critical_low",
                rule_type=rule_type,
            )
        )

    if critical_high is not None and numeric_value > critical_high:
        alerts.append(
            make_alert(
                channel=channel,
                severity="critical",
                reason=threshold_reason(category, "high", "critical"),
                rule_id="threshold_critical_high",
                rule_type=rule_type,
            )
        )

    if warning_low is not None and numeric_value < warning_low:
        alerts.append(
            make_alert(
                channel=channel,
                severity="warning",
                reason=threshold_reason(category, "low", "warning"),
                rule_id="threshold_warning_low",
                rule_type=rule_type,
            )
        )

    if warning_high is not None and numeric_value > warning_high:
        alerts.append(
            make_alert(
                channel=channel,
                severity="warning",
                reason=threshold_reason(category, "high", "warning"),
                rule_id="threshold_warning_high",
                rule_type=rule_type,
            )
        )

    return alerts


def build_zero_flow_alert(
    channel: dict[str, Any],
    channel_config: dict[str, Any],
    numeric_value: float,
) -> dict[str, Any] | None:
    """Evaluate the temporary current-value zero flow rule."""
    if channel.get("category") != "flow":
        return None

    configured_severity = channel_config.get("zero_flow_severity")
    zero_flow_enabled = bool(channel_config.get("zero_flow_enabled"))

    if not configured_severity and not zero_flow_enabled:
        return None

    severity = normalize_severity(configured_severity, default="warning")
    epsilon = parse_optional_number(channel_config.get("zero_flow_epsilon"))

    if epsilon is None:
        epsilon = 0.000001

    if abs(numeric_value) <= epsilon:
        return make_alert(
            channel=channel,
            severity=severity,
            reason=(
                "Η τρέχουσα ροή είναι μηδενική ή σχεδόν μηδενική. "
                "Προσωρινός κανόνας Φάσης 5: ελέγχεται μόνο η τρέχουσα τιμή, "
                "όχι η διάρκεια μηδενικής ροής."
            ),
            rule_id="zero_flow_current_value",
            rule_type="zero_flow",
        )

    return None


def choose_worst_alert(alerts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-priority alert from a list."""
    if not alerts:
        return None

    return sorted(
        alerts,
        key=lambda alert: SEVERITY_PRIORITY.get(alert.get("severity", "unknown"), 99),
    )[0]


def evaluate_channel(
    channel: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one channel and return its operational status."""
    config_data = config if config is not None else load_channels_config()
    cnl_num = channel.get("cnl_num")
    category = channel.get("category") or "unknown"
    channel_config = get_channel_config(cnl_num, config=config_data)

    numeric_value = parse_number(channel.get("current_value"))

    invalid_alert = build_invalid_value_alert(
        channel=channel,
        channel_config=channel_config,
        numeric_value=numeric_value,
    )

    if invalid_alert:
        return invalid_alert

    alerts: list[dict[str, Any]] = []

    if numeric_value is not None:
        alerts.extend(
            build_threshold_alerts(
                channel=channel,
                channel_config=channel_config,
                numeric_value=numeric_value,
            )
        )

        zero_flow_alert = build_zero_flow_alert(
            channel=channel,
            channel_config=channel_config,
            numeric_value=numeric_value,
        )

        if zero_flow_alert:
            alerts.append(zero_flow_alert)

    worst_alert = choose_worst_alert(alerts)

    if worst_alert:
        return worst_alert

    return make_alert(
        channel=channel,
        severity="normal",
        reason="Δεν εντοπίστηκε ενεργή επιχειρησιακή προειδοποίηση.",
        rule_id="normal",
        rule_type="normal",
    )


def evaluate_channels(
    channels: list[dict[str, Any]],
    *,
    include_normal: bool = False,
) -> list[dict[str, Any]]:
    """Evaluate many channels and return operational alerts/statuses."""
    config = load_channels_config()
    results = [evaluate_channel(channel, config=config) for channel in channels]

    if not include_normal:
        results = [item for item in results if item["severity"] != "normal"]

    return sort_alerts(results)


def sort_alerts(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort alerts by severity and then by channel number."""
    return sorted(
        alerts,
        key=lambda alert: (
            SEVERITY_PRIORITY.get(alert.get("severity", "unknown"), 99),
            alert.get("cnl_num") or 0,
        ),
    )


def build_overview(channels: list[dict[str, Any]], fetched_at: str | None) -> dict[str, Any]:
    """Build operational overview summary from evaluated channel statuses."""
    evaluations = evaluate_channels(channels, include_normal=True)

    severity_counts = {
        "normal": 0,
        "warning": 0,
        "critical": 0,
        "unknown": 0,
    }

    for evaluation in evaluations:
        severity = evaluation.get("severity") or "unknown"
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    invalid_count = sum(
        1 for evaluation in evaluations if evaluation.get("rule_type") == "invalid_value"
    )

    scada_normal_count = sum(1 for channel in channels if is_scada_status_normal(channel))
    scada_abnormal_count = len(channels) - scada_normal_count

    alerts_count = sum(
        1 for evaluation in evaluations if evaluation.get("severity") != "normal"
    )

    return {
        "total_channels": len(channels),
        "normal_count": severity_counts["normal"],
        "warning_count": severity_counts["warning"],
        "critical_count": severity_counts["critical"],
        "unknown_count": severity_counts["unknown"],
        "invalid_count": invalid_count,
        "scada_normal_count": scada_normal_count,
        "scada_abnormal_count": scada_abnormal_count,
        "last_refresh": fetched_at,
        "fetched_at": fetched_at,
        "alerts_count": alerts_count,
    }