from pathlib import Path
import xml.etree.ElementTree as ET

from app.metadata.models import ChannelMetadata, CommLineMetadata, DeviceMetadata


BASE_XML_DIR = Path(__file__).resolve().parents[2] / "scada_project" / "BaseXML"

XSI_NIL_ATTR = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def _get_text(element: ET.Element, child_name: str) -> str | None:
    """Return stripped child text, handling missing and nil XML nodes."""
    child = element.find(child_name)

    if child is None:
        return None

    if child.attrib.get(XSI_NIL_ATTR) == "true":
        return None

    if child.text is None:
        return None

    value = child.text.strip()
    return value if value else None


def _to_int(value: str | None) -> int | None:
    """Convert a string value to int when possible."""
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _to_bool(value: str | None, default: bool = False) -> bool:
    """Convert common XML boolean text values to bool."""
    if value is None:
        return default

    return value.strip().lower() in {"true", "1", "yes"}


def _load_xml_root(file_name: str) -> ET.Element:
    """Load an XML file from the BaseXML directory and return its root."""
    file_path = BASE_XML_DIR / file_name

    if not file_path.exists():
        raise FileNotFoundError(f"Required XML file not found: {file_path}")

    return ET.parse(file_path).getroot()


def load_comm_lines() -> dict[int, CommLineMetadata]:
    """Load communication lines from CommLine.xml."""
    root = _load_xml_root("CommLine.xml")
    comm_lines: dict[int, CommLineMetadata] = {}

    for item in root.findall("CommLine"):
        comm_line_num = _to_int(_get_text(item, "CommLineNum"))

        if comm_line_num is None:
            continue

        comm_lines[comm_line_num] = CommLineMetadata(
            comm_line_num=comm_line_num,
            name=_get_text(item, "Name"),
        )

    return comm_lines


def load_devices() -> dict[int, DeviceMetadata]:
    """Load devices from Device.xml."""
    root = _load_xml_root("Device.xml")
    devices: dict[int, DeviceMetadata] = {}

    for item in root.findall("Device"):
        device_num = _to_int(_get_text(item, "DeviceNum"))

        if device_num is None:
            continue

        devices[device_num] = DeviceMetadata(
            device_num=device_num,
            name=_get_text(item, "Name"),
            comm_line_num=_to_int(_get_text(item, "CommLineNum")),
        )

    return devices


def load_channels_metadata() -> list[ChannelMetadata]:
    """Load channels from Cnl.xml and enrich them with device and comm line metadata."""
    root = _load_xml_root("Cnl.xml")

    devices = load_devices()
    comm_lines = load_comm_lines()

    channels: list[ChannelMetadata] = []

    for item in root.findall("Cnl"):
        cnl_num = _to_int(_get_text(item, "CnlNum"))

        if cnl_num is None:
            continue

        device_num = _to_int(_get_text(item, "DeviceNum"))
        device = devices.get(device_num) if device_num is not None else None

        comm_line_num = device.comm_line_num if device else None
        comm_line = comm_lines.get(comm_line_num) if comm_line_num is not None else None

        channels.append(
            ChannelMetadata(
                cnl_num=cnl_num,
                active=_to_bool(_get_text(item, "Active")),
                name=_get_text(item, "Name"),
                tag_code=_get_text(item, "TagCode"),
                device_num=device_num,
                device_name=device.name if device else None,
                comm_line_num=comm_line_num,
                comm_line_name=comm_line.name if comm_line else None,
                cnl_type_id=_to_int(_get_text(item, "CnlTypeID")),
                format_id=_to_int(_get_text(item, "FormatID")),
                unit_id=_to_int(_get_text(item, "UnitID")),
            )
        )

    channels.sort(key=lambda channel: channel.cnl_num)
    return channels