from pathlib import Path
from typing import Any
import json
import re
import unicodedata


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CHANNELS_CONFIG_PATH = BASE_DIR / "config" / "channels_config.json"

CATEGORY_LABELS: dict[str, str] = {
    "flow": "Ροή",
    "cumulative_flow": "Υδρόμετρο / Σύνολο Ροής",
    "level": "Στάθμη",
    "quality": "Ποιότητα",
    "motor_current": "Ένταση Κινητήρα",
    "pressure": "Πίεση",
    "unknown": "Άγνωστο",
}

CATEGORY_ORDER: list[str] = [
    "flow",
    "cumulative_flow",
    "level",
    "quality",
    "motor_current",
    "pressure",
    "unknown",
]

DEFAULT_UNITS_BY_CATEGORY: dict[str, str | None] = {
    "flow": "m³/h",
    "cumulative_flow": "m³",
    "level": "m",
    "quality": "%",
    "motor_current": "A",
    "pressure": "bar",
    "unknown": None,
}


def normalize_text(value: Any) -> str:
    """Normalize text for simple Greek/English keyword matching."""
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.lower().strip()


def get_category_label(category: str | None) -> str:
    """Return the Greek label for an internal category code."""
    return CATEGORY_LABELS.get(category or "unknown", CATEGORY_LABELS["unknown"])


def is_valid_category(category: Any) -> bool:
    """Check if a value is one of the supported internal category codes."""
    return isinstance(category, str) and category in CATEGORY_LABELS


def infer_category(name: Any, tag_code: Any) -> str:
    """Infer a channel category from channel name and tag code."""
    normalized_name = normalize_text(name)
    normalized_tag = normalize_text(tag_code)
    combined = f"{normalized_name} {normalized_tag}"

    # Cumulative/total flow must be checked before plain flow.
    if (
        "συνολο ροης" in combined
        or ("συνολο" in combined and ("ροη" in combined or "flow" in combined))
        or "ενδειξη μετρητη" in combined
        or "accum" in combined
        or "cumulative" in combined
        or "total flow" in combined
        or "_tot" in combined
        or " total" in combined
    ):
        return "cumulative_flow"

    if "σταθμη" in combined or "level" in combined:
        return "level"

    if "ποιοτητα" in combined or "quality" in combined:
        return "quality"

    if "πιεση" in combined or "pressure" in combined:
        return "pressure"

    if (
        "ενταση" in combined
        or "ampere" in combined
        or "amper" in combined
        or re.match(r"^cp[\w-]*$", normalized_tag)
    ):
        return "motor_current"

    if "ροη" in combined or "flow" in combined:
        return "flow"

    return "unknown"


def load_channels_config(
    config_path: str | Path = DEFAULT_CHANNELS_CONFIG_PATH,
) -> dict[str, Any]:
    """Load local channel configuration from JSON."""
    path = Path(config_path)

    if not path.exists():
        return {"channels": {}, "relations": []}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        return {"channels": {}, "relations": []}

    channels = data.get("channels", {})

    if isinstance(channels, list):
        normalized_channels = {}

        for item in channels:
            if not isinstance(item, dict):
                continue

            cnl_num = item.get("cnl_num")
            if cnl_num is None:
                continue

            normalized_channels[str(cnl_num)] = item

        data["channels"] = normalized_channels

    elif isinstance(channels, dict):
        data["channels"] = {str(key): value for key, value in channels.items()}
    else:
        data["channels"] = {}

    if not isinstance(data.get("relations"), list):
        data["relations"] = []

    return data


def get_channel_config(
    cnl_num: int | str | None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return manual config for one channel, if it exists."""
    if cnl_num is None:
        return {}

    config_data = config if config is not None else load_channels_config()
    channels = config_data.get("channels", {})

    channel_config = channels.get(str(cnl_num), {}) if isinstance(channels, dict) else {}
    return channel_config if isinstance(channel_config, dict) else {}


def _clean_optional_text(value: Any) -> str | None:
    """Return a clean string or None."""
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def build_channel_classification(
    channel: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build category/display data for one channel."""
    cnl_num = channel.get("cnl_num", channel.get("cnlNum"))
    config_data = config if config is not None else load_channels_config()
    channel_config = get_channel_config(cnl_num, config=config_data)

    inferred_category = infer_category(
        name=channel.get("name"),
        tag_code=channel.get("tag_code"),
    )

    configured_category = channel_config.get("category")
    category = configured_category if is_valid_category(configured_category) else inferred_category

    configured_default_units = config_data.get("default_units_by_category", {})
    default_units = {
        **DEFAULT_UNITS_BY_CATEGORY,
        **configured_default_units,
    }

    unit = (
        _clean_optional_text(channel_config.get("unit"))
        or _clean_optional_text(channel.get("unit"))
        or _clean_optional_text(default_units.get(category))
    )

    return {
        "category": category,
        "category_label": get_category_label(category),
        "display_name": _clean_optional_text(channel_config.get("display_name")),
        "unit": unit,
        "installation": _clean_optional_text(channel_config.get("installation")),
        "inferred_category": inferred_category,
        "has_manual_config": bool(channel_config),
    }


def build_category_summary(channels: list[dict[str, Any]]) -> dict[str, Any]:
    """Build channel counts per category."""
    config = load_channels_config()
    counts = {category: 0 for category in CATEGORY_ORDER}

    for channel in channels:
        classification = build_channel_classification(channel, config=config)
        category = classification["category"]
        counts[category] = counts.get(category, 0) + 1

    categories = [
        {
            "category": category,
            "category_label": get_category_label(category),
            "count": counts.get(category, 0),
        }
        for category in CATEGORY_ORDER
    ]

    return {
        "total": sum(counts.values()),
        "counts": counts,
        "categories": categories,
    }