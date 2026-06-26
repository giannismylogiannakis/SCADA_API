from __future__ import annotations

from math import isfinite
from typing import Any

from app.analytics.alarm_catalog import (
    get_catalog_channel_override,
    get_catalog_rules_for_category,
    load_alarms_config,
)
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

THRESHOLD_KEYS = {
    "warning_low",
    "critical_low",
    "warning_high",
    "critical_high",
}


class RuleEvaluationContext:
    """Small context object passed around during rule evaluation."""

    def __init__(
        self,
        *,
        channel: dict[str, Any],
        channel_config: dict[str, Any],
        rule: dict[str, Any],
        numeric_value: float | None,
    ) -> None:
        self.channel = channel
        self.channel_config = channel_config
        self.rule = rule
        self.numeric_value = numeric_value
        self.statistics = extract_statistics(channel)


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
    """Parse a numeric current/statistical value safely."""
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


def round_metric(value: Any, digits: int = 3) -> float | None:
    """Round numeric metrics for compact API output."""
    numeric_value = parse_number(value)

    if numeric_value is None:
        return None

    return round(numeric_value, digits)


def get_nested_number(data: dict[str, Any], keys: list[str]) -> float | None:
    """Return the first numeric value found in a nested dictionary."""
    for key in keys:
        value = data.get(key)
        numeric_value = parse_optional_number(value)

        if numeric_value is not None:
            return numeric_value

    return None


def get_channel_setting(channel_config: dict[str, Any], key: str) -> Any:
    """Read a setting from flat config, thresholds, alarm_settings, or rules."""
    if key in channel_config:
        return channel_config.get(key)

    for nested_key in ("thresholds", "alarm_settings", "alarms", "cumulative"):
        nested = channel_config.get(nested_key)
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)

    return None


def get_threshold(channel_config: dict[str, Any], key: str) -> float | None:
    """Read a threshold either from flat config or nested thresholds."""
    return parse_optional_number(get_channel_setting(channel_config, key))


def is_truthy_config(value: Any) -> bool:
    """Interpret config values that represent true."""
    if isinstance(value, bool):
        return value

    if isinstance(value, int | float):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}

    return False


def is_falsey_config(value: Any) -> bool:
    """Interpret config values that represent false."""
    if isinstance(value, bool):
        return not value

    if isinstance(value, int | float):
        return value == 0

    if isinstance(value, str):
        return value.strip().lower() in {"false", "0", "no", "n", "off"}

    return False


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


def extract_statistics(channel: dict[str, Any]) -> dict[str, Any]:
    """Return statistics from a channel regardless of nesting style."""
    statistics = channel.get("statistics")

    if isinstance(statistics, dict):
        return statistics

    result: dict[str, Any] = {}

    for key in (
        "has_history",
        "latest_history_value",
        "latest_history_ts",
        "avg_1h",
        "avg_24h",
        "avg_7d",
        "min_24h",
        "max_24h",
        "delta_1h",
        "delta_24h",
        "delta_3d",
        "deviation_from_avg_1h",
        "deviation_percent_from_avg_1h",
    ):
        if key in channel:
            result[key] = channel.get(key)

    return result


def get_metric_value(channel: dict[str, Any], statistics: dict[str, Any], metric_name: str | None) -> float | None:
    """Read a metric from statistics first and then from the channel."""
    if not metric_name:
        return None

    if metric_name in statistics:
        return parse_optional_number(statistics.get(metric_name))

    return parse_optional_number(channel.get(metric_name))


def get_rule_channel_overrides(
    *,
    rule_id: str,
    cnl_num: int | str | None,
    channel_config: dict[str, Any],
    alarms_config: dict[str, Any],
) -> dict[str, Any]:
    """Merge per-channel rule overrides from channels_config and alarms_config."""
    merged: dict[str, Any] = {}

    channel_rules = channel_config.get("rules")
    if isinstance(channel_rules, dict):
        override = channel_rules.get(rule_id)
        if isinstance(override, dict):
            merged.update(override)

    rule_overrides = channel_config.get("rule_overrides")
    if isinstance(rule_overrides, dict):
        override = rule_overrides.get(rule_id)
        if isinstance(override, dict):
            merged.update(override)

    catalog_override = get_catalog_channel_override(cnl_num, catalog=alarms_config)
    catalog_rules = catalog_override.get("rules")
    if isinstance(catalog_rules, dict):
        override = catalog_rules.get(rule_id)
        if isinstance(override, dict):
            merged.update(override)

    return merged


def is_rule_disabled_for_channel(
    *,
    rule_id: str,
    cnl_num: int | str | None,
    channel_config: dict[str, Any],
    alarms_config: dict[str, Any],
) -> bool:
    """Check disabled_rules lists from channel and catalog overrides."""
    disabled_rules = channel_config.get("disabled_rules", [])
    if isinstance(disabled_rules, list) and rule_id in disabled_rules:
        return True

    catalog_override = get_catalog_channel_override(cnl_num, catalog=alarms_config)
    catalog_disabled_rules = catalog_override.get("disabled_rules", [])
    if isinstance(catalog_disabled_rules, list) and rule_id in catalog_disabled_rules:
        return True

    return False


def build_effective_rule(
    *,
    rule: dict[str, Any],
    channel: dict[str, Any],
    channel_config: dict[str, Any],
    alarms_config: dict[str, Any],
) -> dict[str, Any] | None:
    """Apply channel overrides and applicability checks to one catalog rule."""
    cnl_num = channel.get("cnl_num")
    category = channel.get("category") or "unknown"
    rule_id = str(rule.get("rule_id") or "").strip()

    if not rule_id:
        return None

    if is_rule_disabled_for_channel(
        rule_id=rule_id,
        cnl_num=cnl_num,
        channel_config=channel_config,
        alarms_config=alarms_config,
    ):
        return None

    effective_rule = dict(rule)
    effective_rule.update(
        get_rule_channel_overrides(
            rule_id=rule_id,
            cnl_num=cnl_num,
            channel_config=channel_config,
            alarms_config=alarms_config,
        )
    )

    if effective_rule.get("enabled") is False:
        return None

    applies_to = effective_rule.get("applies_to")
    if isinstance(applies_to, dict):
        categories = applies_to.get("categories") or applies_to.get("category")
        if isinstance(categories, str):
            categories = [categories]

        if isinstance(categories, list) and categories and category not in categories and "all" not in categories:
            return None

        channel_nums = applies_to.get("channel_nums") or applies_to.get("channels")
        if isinstance(channel_nums, list) and channel_nums:
            if str(cnl_num) not in {str(item) for item in channel_nums}:
                return None

        excluded = applies_to.get("excluded_channel_nums") or applies_to.get("excluded_channels")
        if isinstance(excluded, list) and str(cnl_num) in {str(item) for item in excluded}:
            return None

    excluded_channels = effective_rule.get("excluded_channels") or effective_rule.get("excluded_channel_nums")
    if isinstance(excluded_channels, list) and str(cnl_num) in {str(item) for item in excluded_channels}:
        return None

    requires_flag = effective_rule.get("requires_channel_flag")
    if requires_flag and not is_truthy_config(get_channel_setting(channel_config, str(requires_flag))):
        return None

    return effective_rule


def format_percent(value: float | None) -> str:
    """Format percent values for operator-facing text."""
    if value is None:
        return "—"

    rounded = round(abs(value), 1)
    if rounded.is_integer():
        return str(int(rounded))

    return str(rounded).replace(".", ",")


def fill_reason_template(template: str, metrics: dict[str, Any]) -> str:
    """Safely fill a Greek reason template."""
    values = {
        **metrics,
        "deviation_percent_abs": format_percent(metrics.get("deviation_percent")),
        "deviation_percent": format_percent(metrics.get("deviation_percent")),
        "baseline_label": metrics.get("baseline_label") or "baseline",
    }

    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return template


def make_alert(
    *,
    channel: dict[str, Any],
    severity: str,
    reason: str,
    rule_id: str,
    rule_type: str,
    priority: int = 100,
    technical_reason: str | None = None,
    metrics: dict[str, Any] | None = None,
    baseline: str | None = None,
    expected_value: float | None = None,
    deviation_percent: float | None = None,
    ) -> dict[str, Any]:
    """Create a normalized alert/evaluation object."""
    cnl_num = channel.get("cnl_num")
    category = channel.get("category") or "unknown"
    cleaned_metrics = metrics or {}
    statistics = extract_statistics(channel)

    return {
        "alert_id": f"{rule_id}:{cnl_num}",
        "rule_id": rule_id,
        "rule_type": rule_type,
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
        "technical_reason": technical_reason,
        "details": technical_reason,
        "metrics": cleaned_metrics,
        "statistics": statistics,
        "avg_1h": statistics.get("avg_1h"),
        "avg_24h": statistics.get("avg_24h"),
        "avg_7d": statistics.get("avg_7d"),
        "min_24h": statistics.get("min_24h"),
        "max_24h": statistics.get("max_24h"),
        "delta_1h": statistics.get("delta_1h"),
        "delta_24h": statistics.get("delta_24h"),
        "delta_3d": statistics.get("delta_3d"),
        "baseline": baseline,
        "expected_value": expected_value,
        "deviation_percent": deviation_percent,
        "scada_status": channel.get("scada_status"),
        "scada_status_text": channel.get("scada_status_text"),
        "fetched_at": channel.get("fetched_at"),
        "last_update": channel.get("last_update"),
        "priority": priority,
    }


def get_rule_severity(rule: dict[str, Any], category: str, default: str = "warning") -> str:
    """Return rule severity, supporting severity_by_category."""
    severity_by_category = rule.get("severity_by_category")

    if isinstance(severity_by_category, dict):
        severity = severity_by_category.get(category)
        if severity:
            return normalize_severity(severity, default=default)

    return normalize_severity(rule.get("severity"), default=default)


def evaluate_invalid_value(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate invalid/undefined SCADA values and non-numeric current values."""
    category = ctx.channel.get("category") or "unknown"
    severity = get_rule_severity(ctx.rule, category, default="warning")
    priority = int(ctx.rule.get("priority", 10))

    if not is_scada_status_valid(ctx.channel):
        reason = str(
            ctx.rule.get("reason_template")
            or "Η τιμή του καναλιού δεν είναι έγκυρη σύμφωνα με το SCADA."
        )
        metrics = {
            "scada_status": ctx.channel.get("scada_status"),
            "scada_status_text": ctx.channel.get("scada_status_text"),
        }
        return make_alert(
            channel=ctx.channel,
            severity=severity,
            reason=reason,
            rule_id=ctx.rule["rule_id"],
            rule_type="invalid_value",
            priority=priority,
            technical_reason=ctx.rule.get("technical_description"),
            metrics=metrics,
        )

    if ctx.numeric_value is None:
        metrics = {"current_value": ctx.channel.get("current_value")}
        return make_alert(
            channel=ctx.channel,
            severity=severity,
            reason="Η τιμή του καναλιού δεν είναι αριθμητική και δεν μπορεί να αξιολογηθεί.",
            rule_id="non_numeric_value",
            rule_type="invalid_value",
            priority=priority,
            technical_reason="Current value could not be parsed as a finite number.",
            metrics=metrics,
        )

    return None


def threshold_reason(category: str, bound: str, severity: str) -> str:
    """Build Greek reason text for threshold violations."""
    is_low = bound == "low"
    is_critical = severity == "critical"

    if category == "level":
        if is_low and is_critical:
            return "Η στάθμη είναι κάτω από το κρίσιμο όριο."
        if is_low:
            return "Η στάθμη είναι κάτω από το όριο προειδοποίησης."
        if is_critical:
            return "Η στάθμη είναι πάνω από το κρίσιμο όριο."
        return "Η στάθμη είναι πάνω από το όριο προειδοποίησης."

    if category == "quality":
        if is_low and is_critical:
            return "Η ποιότητα είναι κάτω από το κρίσιμο όριο."
        if is_low:
            return "Η ποιότητα είναι κάτω από το όριο προειδοποίησης."
        if is_critical:
            return "Η ποιότητα είναι πάνω από το κρίσιμο όριο."
        return "Η ποιότητα είναι πάνω από το όριο προειδοποίησης."

    if category == "motor_current":
        if is_low and is_critical:
            return "Η ένταση κινητήρα είναι κάτω από το κρίσιμο όριο."
        if is_low:
            return "Η ένταση κινητήρα είναι κάτω από το όριο προειδοποίησης."
        if is_critical:
            return "Η ένταση κινητήρα είναι πάνω από το κρίσιμο όριο."
        return "Η ένταση κινητήρα είναι πάνω από το όριο προειδοποίησης."

    if category == "pressure":
        if is_low and is_critical:
            return "Η πίεση είναι κάτω από το κρίσιμο όριο."
        if is_low:
            return "Η πίεση είναι κάτω από το όριο προειδοποίησης."
        if is_critical:
            return "Η πίεση είναι πάνω από το κρίσιμο όριο."
        return "Η πίεση είναι πάνω από το όριο προειδοποίησης."

    if is_low and is_critical:
        return "Η τιμή είναι κάτω από το κρίσιμο όριο."
    if is_low:
        return "Η τιμή είναι κάτω από το όριο προειδοποίησης."
    if is_critical:
        return "Η τιμή είναι πάνω από το κρίσιμο όριο."

    return "Η τιμή είναι πάνω από το όριο προειδοποίησης."


def evaluate_static_threshold(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate static warning/critical thresholds from channels_config."""
    if ctx.numeric_value is None:
        return None

    category = ctx.channel.get("category") or "unknown"
    priority = int(ctx.rule.get("priority", 20))
    checks = [
        ("critical_low", "critical", "low", lambda value, limit: value < limit),
        ("critical_high", "critical", "high", lambda value, limit: value > limit),
        ("warning_low", "warning", "low", lambda value, limit: value < limit),
        ("warning_high", "warning", "high", lambda value, limit: value > limit),
    ]

    alerts: list[dict[str, Any]] = []

    for threshold_key, severity, bound, predicate in checks:
        limit = get_threshold(ctx.channel_config, threshold_key)

        if limit is None or not predicate(ctx.numeric_value, limit):
            continue

        metrics = {
            "current_value": round_metric(ctx.numeric_value),
            "threshold_key": threshold_key,
            "threshold_value": round_metric(limit),
        }
        alerts.append(
            make_alert(
                channel=ctx.channel,
                severity=severity,
                reason=threshold_reason(category, bound, severity),
                rule_id=f"threshold_{threshold_key}",
                rule_type="level_out_of_bounds" if category == "level" else "static_threshold",
                priority=priority,
                technical_reason=(
                    f"{ctx.numeric_value} violates {threshold_key}={limit}. "
                    f"Rule catalog source: {ctx.rule.get('rule_id')}"
                ),
                metrics=metrics,
            )
        )

    return choose_worst_alert(alerts)

def evaluate_value_below_threshold(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate a catalog-defined low threshold for a whole category."""
    if ctx.numeric_value is None:
        return None

    warning_below = parse_optional_number(ctx.rule.get("warning_below"))
    if warning_below is None:
        warning_below = parse_optional_number(ctx.rule.get("warning_threshold"))

    critical_below = parse_optional_number(ctx.rule.get("critical_below"))
    if critical_below is None:
        critical_below = parse_optional_number(ctx.rule.get("critical_threshold"))

    severity = None
    threshold = None

    if critical_below is not None and ctx.numeric_value < critical_below:
        severity = "critical"
        threshold = critical_below
    elif warning_below is not None and ctx.numeric_value < warning_below:
        severity = "warning"
        threshold = warning_below

    if severity is None:
        return None

    priority = int(ctx.rule.get("priority", 40))

    if severity == "critical":
        reason = str(
            ctx.rule.get("critical_reason_template")
            or ctx.rule.get("reason_template")
            or "Η τιμή είναι κάτω από το κρίσιμο όριο."
        )
    else:
        reason = str(
            ctx.rule.get("warning_reason_template")
            or ctx.rule.get("reason_template")
            or "Η τιμή είναι κάτω από το όριο προειδοποίησης."
        )

    metrics = {
        "current_value": round_metric(ctx.numeric_value),
        "threshold": round_metric(threshold),
        "warning_below": round_metric(warning_below),
        "critical_below": round_metric(critical_below),
    }

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=reason,
        rule_id=ctx.rule["rule_id"],
        rule_type="value_below_threshold",
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
    )


def evaluate_zero_value(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate zero or near-zero value rules."""
    if ctx.numeric_value is None:
        return None

    epsilon = get_nested_number(
        ctx.rule,
        ["zero_epsilon", "epsilon"],
    )

    if epsilon is None:
        epsilon = parse_optional_number(get_channel_setting(ctx.channel_config, "zero_flow_epsilon"))

    if epsilon is None:
        epsilon = 0.000001

    if abs(ctx.numeric_value) > epsilon:
        return None

    category = ctx.channel.get("category") or "unknown"
    severity = get_rule_severity(ctx.rule, category, default="warning")
    priority = int(ctx.rule.get("priority", 50))
    reason = str(ctx.rule.get("reason_template") or "Η τιμή είναι μηδενική.")
    metrics = {
        "current_value": round_metric(ctx.numeric_value),
        "epsilon": round_metric(epsilon, digits=6),
    }

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=reason,
        rule_id=ctx.rule["rule_id"],
        rule_type="zero_value",
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
    )


def evaluate_negative_value(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate negative current values when not explicitly allowed."""
    if ctx.numeric_value is None:
        return None

    if is_truthy_config(get_channel_setting(ctx.channel_config, "allow_negative")):
        return None

    critical_below = parse_optional_number(ctx.rule.get("critical_below"))
    if critical_below is None:
        critical_below = 0.0

    if ctx.numeric_value >= critical_below:
        return None

    category = ctx.channel.get("category") or "unknown"
    severity = get_rule_severity(ctx.rule, category, default="warning")
    priority = int(ctx.rule.get("priority", 30))
    reason = str(ctx.rule.get("reason_template") or "Η τιμή είναι αρνητική ενώ δεν αναμένεται.")
    metrics = {
        "current_value": round_metric(ctx.numeric_value),
        "critical_below": round_metric(critical_below),
    }

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=reason,
        rule_id=ctx.rule["rule_id"],
        rule_type="negative_value",
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
    )


def get_deviation_percent(current_value: float, baseline_value: float) -> float | None:
    """Return signed percent deviation from baseline."""
    if baseline_value == 0:
        return None

    return ((current_value - baseline_value) / baseline_value) * 100


def get_deviation_severity(
    *,
    deviation_abs: float,
    warning_percent: float | None,
    critical_percent: float | None,
) -> str | None:
    """Return severity based on warning/critical percent thresholds."""
    if critical_percent is not None and deviation_abs >= critical_percent:
        return "critical"

    if warning_percent is not None and deviation_abs >= warning_percent:
        return "warning"

    return None


def evaluate_deviation_from_baseline(
    ctx: RuleEvaluationContext,
    *,
    mode: str,
) -> dict[str, Any] | None:
    """Evaluate signed or absolute percent deviation from a historical baseline."""
    if ctx.numeric_value is None:
        return None

    baseline_key = ctx.rule.get("baseline")
    baseline_value = get_metric_value(ctx.channel, ctx.statistics, str(baseline_key or ""))

    if baseline_value is None:
        return None

    min_baseline = parse_optional_number(ctx.rule.get("min_baseline_value"))
    if min_baseline is None:
        min_baseline = 0.000001

    allow_negative_baseline = is_truthy_config(ctx.rule.get("allow_negative_baseline"))

    if allow_negative_baseline:
        if abs(baseline_value) <= min_baseline:
            return None
    else:
        if baseline_value <= min_baseline:
            return None

    deviation_percent = get_deviation_percent(ctx.numeric_value, baseline_value)

    if deviation_percent is None:
        return None

    if mode == "below" and deviation_percent >= 0:
        return None

    if mode == "above" and deviation_percent <= 0:
        return None

    warning_percent = parse_optional_number(ctx.rule.get("warning_deviation_percent"))
    critical_percent = parse_optional_number(ctx.rule.get("critical_deviation_percent"))

    severity = get_deviation_severity(
        deviation_abs=abs(deviation_percent),
        warning_percent=warning_percent,
        critical_percent=critical_percent,
    )

    if severity is None:
        return None

    priority = int(ctx.rule.get("priority", 80))

    metrics = {
        "current_value": round_metric(ctx.numeric_value),
        "baseline": baseline_key,
        "baseline_label": ctx.rule.get("baseline_label") or baseline_key,
        "baseline_value": round_metric(baseline_value),
        "deviation_percent": round(deviation_percent, 3),
        "warning_deviation_percent": warning_percent,
        "critical_deviation_percent": critical_percent,
    }

    template = str(
        ctx.rule.get("reason_template")
        or "Η τιμή αποκλίνει σημαντικά από το ιστορικό baseline."
    )

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=fill_reason_template(template, metrics),
        rule_id=ctx.rule["rule_id"],
        rule_type=ctx.rule.get("condition_type", "deviation_from_baseline"),
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
        baseline=str(baseline_key) if baseline_key else None,
        expected_value=round_metric(baseline_value),
        deviation_percent=round(deviation_percent, 3),
    )


def evaluate_delta_negative(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate negative cumulative deltas."""
    delta_field = str(ctx.rule.get("delta_field") or "delta_1h")
    delta_value = get_metric_value(ctx.channel, ctx.statistics, delta_field)

    if delta_value is None:
        return None

    epsilon = parse_optional_number(ctx.rule.get("min_delta_epsilon"))
    if epsilon is None:
        epsilon = 0.000001

    if delta_value >= -abs(epsilon):
        return None

    category = ctx.channel.get("category") or "unknown"
    severity = get_rule_severity(ctx.rule, category, default="warning")
    priority = int(ctx.rule.get("priority", 30))
    reason = str(ctx.rule.get("reason_template") or "Η μεταβολή είναι αρνητική.")
    metrics = {
        "delta_field": delta_field,
        "delta_value": round_metric(delta_value),
        "epsilon": round_metric(epsilon, digits=6),
    }

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=reason,
        rule_id=ctx.rule["rule_id"],
        rule_type="delta_negative",
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
    )


def evaluate_delta_below_min(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate zero or very small delta when movement is expected."""
    delta_field = str(ctx.rule.get("delta_field") or "delta_24h")
    delta_value = get_metric_value(ctx.channel, ctx.statistics, delta_field)

    if delta_value is None:
        return None

    warning_min = parse_optional_number(ctx.rule.get("warning_min_delta"))
    critical_min = parse_optional_number(ctx.rule.get("critical_min_delta"))

    if warning_min is None:
        warning_min = parse_optional_number(get_channel_setting(ctx.channel_config, f"min_{delta_field}"))

    if critical_min is None:
        critical_min = parse_optional_number(get_channel_setting(ctx.channel_config, f"critical_min_{delta_field}"))

    severity = None
    threshold = None

    if critical_min is not None and abs(delta_value) <= abs(critical_min):
        severity = "critical"
        threshold = critical_min
    elif warning_min is not None and abs(delta_value) <= abs(warning_min):
        severity = "warning"
        threshold = warning_min

    if severity is None:
        return None

    priority = int(ctx.rule.get("priority", 60))
    metrics = {
        "delta_field": delta_field,
        "delta_value": round_metric(delta_value),
        "threshold": round_metric(threshold, digits=6),
    }
    reason = str(ctx.rule.get("reason_template") or "Η μεταβολή είναι μηδενική ή πολύ μικρή.")

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=reason,
        rule_id=ctx.rule["rule_id"],
        rule_type="delta_below_min",
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
    )


def evaluate_delta_above_max(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate excessive delta/spike rules."""
    delta_field = str(ctx.rule.get("delta_field") or "delta_1h")
    delta_value = get_metric_value(ctx.channel, ctx.statistics, delta_field)

    if delta_value is None:
        return None

    max_delta_key = ctx.rule.get("max_delta_config_key")
    max_delta = None

    if max_delta_key:
        max_delta = parse_optional_number(get_channel_setting(ctx.channel_config, str(max_delta_key)))

    if max_delta is None:
        max_delta = parse_optional_number(ctx.rule.get("warning_max_delta"))

    if max_delta is None or delta_value <= max_delta:
        return None

    category = ctx.channel.get("category") or "unknown"
    severity = get_rule_severity(ctx.rule, category, default="warning")
    priority = int(ctx.rule.get("priority", 70))
    metrics = {
        "delta_field": delta_field,
        "delta_value": round_metric(delta_value),
        "max_delta": round_metric(max_delta),
    }
    reason = str(ctx.rule.get("reason_template") or "Η μεταβολή είναι ασυνήθιστα υψηλή.")

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=reason,
        rule_id=ctx.rule["rule_id"],
        rule_type="delta_above_max",
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
    )


def evaluate_rapid_change(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate rapid rise/drop rules using delta fields."""
    delta_field = str(ctx.rule.get("delta_field") or "delta_1h")
    delta_value = get_metric_value(ctx.channel, ctx.statistics, delta_field)

    if delta_value is None:
        return None

    warning_key = ctx.rule.get("warning_abs_delta_config_key")
    critical_key = ctx.rule.get("critical_abs_delta_config_key")
    warning_abs_delta = (
        parse_optional_number(get_channel_setting(ctx.channel_config, str(warning_key)))
        if warning_key
        else parse_optional_number(ctx.rule.get("warning_abs_delta"))
    )
    critical_abs_delta = (
        parse_optional_number(get_channel_setting(ctx.channel_config, str(critical_key)))
        if critical_key
        else parse_optional_number(ctx.rule.get("critical_abs_delta"))
    )

    severity = None
    threshold = None

    if critical_abs_delta is not None and abs(delta_value) >= abs(critical_abs_delta):
        severity = "critical"
        threshold = critical_abs_delta
    elif warning_abs_delta is not None and abs(delta_value) >= abs(warning_abs_delta):
        severity = "warning"
        threshold = warning_abs_delta

    if severity is None:
        return None

    priority = int(ctx.rule.get("priority", 50))
    template_key = "reason_template_increase" if delta_value > 0 else "reason_template_decrease"
    reason = str(
        ctx.rule.get(template_key)
        or ctx.rule.get("reason_template")
        or "Η τιμή μεταβλήθηκε απότομα."
    )
    metrics = {
        "delta_field": delta_field,
        "delta_value": round_metric(delta_value),
        "threshold": round_metric(threshold),
    }

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=reason,
        rule_id=ctx.rule["rule_id"],
        rule_type="rapid_change",
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
    )


def evaluate_absolute_deviation(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Evaluate absolute deviation from a baseline using per-channel limits."""
    if ctx.numeric_value is None:
        return None

    baseline_key = ctx.rule.get("baseline")
    baseline_value = get_metric_value(ctx.channel, ctx.statistics, str(baseline_key or ""))

    if baseline_value is None:
        return None

    warning_key = ctx.rule.get("warning_abs_deviation_config_key")
    critical_key = ctx.rule.get("critical_abs_deviation_config_key")
    warning_abs = (
        parse_optional_number(get_channel_setting(ctx.channel_config, str(warning_key)))
        if warning_key
        else parse_optional_number(ctx.rule.get("warning_abs_deviation"))
    )
    critical_abs = (
        parse_optional_number(get_channel_setting(ctx.channel_config, str(critical_key)))
        if critical_key
        else parse_optional_number(ctx.rule.get("critical_abs_deviation"))
    )

    abs_deviation = abs(ctx.numeric_value - baseline_value)
    severity = None
    threshold = None

    if critical_abs is not None and abs_deviation >= abs(critical_abs):
        severity = "critical"
        threshold = critical_abs
    elif warning_abs is not None and abs_deviation >= abs(warning_abs):
        severity = "warning"
        threshold = warning_abs

    if severity is None:
        return None

    priority = int(ctx.rule.get("priority", 80))
    metrics = {
        "current_value": round_metric(ctx.numeric_value),
        "baseline": baseline_key,
        "baseline_label": ctx.rule.get("baseline_label") or baseline_key,
        "baseline_value": round_metric(baseline_value),
        "abs_deviation": round_metric(abs_deviation),
        "threshold": round_metric(threshold),
    }
    reason = fill_reason_template(
        str(ctx.rule.get("reason_template") or "Η τιμή αποκλίνει σημαντικά από το baseline."),
        metrics,
    )

    return make_alert(
        channel=ctx.channel,
        severity=severity,
        reason=reason,
        rule_id=ctx.rule["rule_id"],
        rule_type="absolute_deviation_from_baseline",
        priority=priority,
        technical_reason=ctx.rule.get("technical_description"),
        metrics=metrics,
        baseline=str(baseline_key) if baseline_key else None,
        expected_value=round_metric(baseline_value),
    )


def evaluate_rule(ctx: RuleEvaluationContext) -> dict[str, Any] | None:
    """Dispatch one effective catalog rule to its evaluator."""
    condition_type = str(ctx.rule.get("condition_type") or "").strip()

    evaluators = {
        "invalid_value": evaluate_invalid_value,
        "static_threshold": evaluate_static_threshold,
        "value_below_threshold": evaluate_value_below_threshold,
        "zero_value": evaluate_zero_value,
        "negative_value": evaluate_negative_value,
        "delta_negative": evaluate_delta_negative,
        "delta_below_min": evaluate_delta_below_min,
        "delta_above_max": evaluate_delta_above_max,
        "rapid_change": evaluate_rapid_change,
        "absolute_deviation_from_baseline": evaluate_absolute_deviation,
    }

    if condition_type == "deviation_below_baseline":
        return evaluate_deviation_from_baseline(ctx, mode="below")

    if condition_type == "deviation_above_baseline":
        return evaluate_deviation_from_baseline(ctx, mode="above")

    if condition_type == "absolute_percent_deviation_from_baseline":
        return evaluate_deviation_from_baseline(ctx, mode="absolute")

    evaluator = evaluators.get(condition_type)

    if evaluator is None:
        return None

    return evaluator(ctx)


def choose_worst_alert(alerts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-priority alert from a list."""
    if not alerts:
        return None

    return sorted(
        alerts,
        key=lambda alert: (
            SEVERITY_PRIORITY.get(alert.get("severity", "unknown"), 99),
            int(alert.get("priority") or 100),
            alert.get("rule_id") or "",
        ),
    )[0]

def get_channel_custom_rules(
    channel_config: dict[str, Any],
    category: str,
) -> list[dict[str, Any]]:
    """Return custom per-channel rules stored in dashboard settings."""
    raw_rules = channel_config.get("custom_rules")

    if not isinstance(raw_rules, list):
        return []

    rules: list[dict[str, Any]] = []

    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            continue

        rule = dict(raw_rule)
        rule_id = str(rule.get("rule_id") or f"custom_{category}_{index + 1}").strip()

        if not rule_id:
            continue

        rule["rule_id"] = rule_id
        rule.setdefault("category", category)
        rule.setdefault("enabled", True)
        rule.setdefault("priority", 90)

        rules.append(rule)

    return rules

def evaluate_channel(
    channel: dict[str, Any],
    config: dict[str, Any] | None = None,
    alarms_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one channel and return its operational status."""
    channel_config_data = config if config is not None else load_channels_config()
    alarm_catalog = alarms_config if alarms_config is not None else load_alarms_config()
    cnl_num = channel.get("cnl_num")
    category = channel.get("category") or "unknown"
    channel_config = get_channel_config(cnl_num, config=channel_config_data)
    numeric_value = parse_number(channel.get("current_value"))

    alerts: list[dict[str, Any]] = []

    catalog_rules = get_catalog_rules_for_category(category, catalog=alarm_catalog)
    custom_rules = get_channel_custom_rules(channel_config, category)

    for rule in [*catalog_rules, *custom_rules]:
        effective_rule = build_effective_rule(
            rule=rule,
            channel=channel,
            channel_config=channel_config,
            alarms_config=alarm_catalog,
        )

        if effective_rule is None:
            continue

        ctx = RuleEvaluationContext(
            channel=channel,
            channel_config=channel_config,
            rule=effective_rule,
            numeric_value=numeric_value,
        )
        alert = evaluate_rule(ctx)

        if alert:
            alerts.append(alert)

        # Do not evaluate business rules if SCADA/current value is invalid.
        if alert and alert.get("rule_type") == "invalid_value":
            break

    worst_alert = choose_worst_alert(alerts)

    if worst_alert:
        return worst_alert

    return make_alert(
        channel=channel,
        severity="normal",
        reason="Δεν εντοπίστηκε ενεργή επιχειρησιακή προειδοποίηση.",
        rule_id="normal",
        rule_type="normal",
        priority=999,
    )


def evaluate_channels(
    channels: list[dict[str, Any]],
    *,
    include_normal: bool = False,
) -> list[dict[str, Any]]:
    """Evaluate many channels and return operational alerts/statuses."""
    config = load_channels_config()
    alarms_config = load_alarms_config()
    results = [
        evaluate_channel(channel, config=config, alarms_config=alarms_config)
        for channel in channels
    ]

    if not include_normal:
        results = [item for item in results if item["severity"] != "normal"]

    return sort_alerts(results)


def sort_alerts(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort alerts by severity, priority, and then by channel number."""
    return sorted(
        alerts,
        key=lambda alert: (
            SEVERITY_PRIORITY.get(alert.get("severity", "unknown"), 99),
            int(alert.get("priority") or 100),
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
