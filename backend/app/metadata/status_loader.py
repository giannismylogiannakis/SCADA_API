from functools import lru_cache
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STATUS_XML_PATH = BASE_DIR / "scada_project" / "BaseXML" / "CnlStatus.xml"


def _text(element: ET.Element, name: str) -> str | None:
    child = element.find(name)
    if child is None or child.text is None:
        return None

    value = child.text.strip()
    return value if value else None


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _bool_or_false(value: str | None) -> bool:
    if value is None:
        return False

    return value.strip().lower() in {"true", "1", "yes", "y"}


@lru_cache(maxsize=1)
def load_cnl_statuses(
    xml_path: str | Path = DEFAULT_STATUS_XML_PATH,
) -> dict[int, dict[str, Any]]:
    """Load Rapid SCADA channel statuses from CnlStatus.xml."""
    path = Path(xml_path)

    if not path.exists():
        return {}

    tree = ET.parse(path)
    root = tree.getroot()

    statuses: dict[int, dict[str, Any]] = {}

    for status_element in root.findall("CnlStatus"):
        status_id = _int_or_none(_text(status_element, "CnlStatusID"))

        if status_id is None:
            continue

        statuses[status_id] = {
            "id": status_id,
            "name": _text(status_element, "Name") or f"Status {status_id}",
            "main_color": _text(status_element, "MainColor"),
            "second_color": _text(status_element, "SecondColor"),
            "back_color": _text(status_element, "BackColor"),
            "severity": _int_or_none(_text(status_element, "Severity")),
            "ack_required": _bool_or_false(_text(status_element, "AckRequired")),
            "description": _text(status_element, "Descr"),
        }

    return statuses