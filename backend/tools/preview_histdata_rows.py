from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


DEFAULT_XML_PATH = Path("scada_project/BaseXML/HistData.xml")
OUTPUT_FILE = Path("histdata_row_preview.json")

MAX_ROWS_SCAN = int(os.getenv("MAX_ROWS_SCAN", "500"))
PREVIEW_FIRST_ROWS = int(os.getenv("PREVIEW_FIRST_ROWS", "80"))
PREVIEW_FIRST_CELLS = int(os.getenv("PREVIEW_FIRST_CELLS", "40"))


def strip_namespace(name: str) -> str:
    """Remove XML namespace from tag or attribute name."""
    if "}" in name:
        return name.split("}", 1)[1]

    return name


def get_attr_by_local_name(attrs: dict[str, str], local_name: str) -> str | None:
    """Get XML attribute by its local name, ignoring namespace."""
    for key, value in attrs.items():
        if strip_namespace(key) == local_name:
            return value

    return None


def compact_text(text: str | None) -> str | None:
    """Normalize whitespace in cell text."""
    if text is None:
        return None

    cleaned = re.sub(r"\s+", " ", text).strip()

    if not cleaned:
        return None

    return cleaned


def parse_row(row_elem: ET.Element) -> tuple[list[Any], list[str | None]]:
    """Parse one SpreadsheetML Row element into cell values and data types."""
    values: list[Any] = []
    data_types: list[str | None] = []
    current_col = 1

    for cell in row_elem:
        if strip_namespace(cell.tag) != "Cell":
            continue

        index_text = get_attr_by_local_name(cell.attrib, "Index")

        if index_text:
            try:
                current_col = int(index_text)
            except ValueError:
                pass

        while len(values) < current_col - 1:
            values.append(None)
            data_types.append(None)

        cell_value = None
        cell_type = None

        for child in cell:
            if strip_namespace(child.tag) == "Data":
                cell_value = compact_text(child.text)
                cell_type = get_attr_by_local_name(child.attrib, "Type")
                break

        values.append(cell_value)
        data_types.append(cell_type)
        current_col += 1

    return values, data_types


def looks_like_date(value: Any) -> bool:
    """Detect common exported date/time values."""
    if value is None:
        return False

    text = str(value)

    patterns = [
        r"^\d{1,2}/\d{1,2}/\d{4}",
        r"^\d{4}-\d{2}-\d{2}",
        r"^\d{1,2}\.\d{1,2}\.\d{4}",
    ]

    return any(re.search(pattern, text) for pattern in patterns)


def count_numeric(values: list[Any]) -> int:
    """Count numeric-looking cells."""
    count = 0

    for value in values:
        if value is None:
            continue

        text = str(value).replace(",", ".")

        try:
            float(text)
            count += 1
        except ValueError:
            pass

    return count


def main() -> None:
    """Preview rows from a large Rapid SCADA SpreadsheetML historical export."""
    xml_path = Path(os.getenv("HISTDATA_XML_PATH", str(DEFAULT_XML_PATH)))

    result: dict[str, Any] = {
        "ok": False,
        "mode": "histdata_spreadsheetml_row_preview",
        "xml_path": str(xml_path),
        "file_exists": xml_path.exists(),
        "file_size_mb": None,
        "max_rows_scan": MAX_ROWS_SCAN,
        "preview_first_rows": PREVIEW_FIRST_ROWS,
        "preview_first_cells": PREVIEW_FIRST_CELLS,
        "rows_seen": 0,
        "preview_rows": [],
        "candidate_data_rows": [],
        "wide_rows": [],
        "parse_error": None,
    }

    if not xml_path.exists():
        result["parse_error"] = "HistData.xml was not found."
        OUTPUT_FILE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"ERROR: File not found: {xml_path}")
        return

    result["file_size_mb"] = round(xml_path.stat().st_size / 1024 / 1024, 2)

    try:
        row_no = 0

        context = ET.iterparse(xml_path, events=("end",))

        for event, elem in context:
            if strip_namespace(elem.tag) != "Row":
                continue

            row_no += 1
            values, data_types = parse_row(elem)

            non_empty_values = [value for value in values if value is not None]
            numeric_count = count_numeric(values)

            row_info = {
                "row_no": row_no,
                "cell_count": len(values),
                "non_empty_count": len(non_empty_values),
                "numeric_count": numeric_count,
                "first_cells": values[:PREVIEW_FIRST_CELLS],
                "first_types": data_types[:PREVIEW_FIRST_CELLS],
            }

            if row_no <= PREVIEW_FIRST_ROWS:
                result["preview_rows"].append(row_info)

            first_non_empty = non_empty_values[0] if non_empty_values else None

            if looks_like_date(first_non_empty) or numeric_count >= 10:
                if len(result["candidate_data_rows"]) < 30:
                    result["candidate_data_rows"].append(row_info)

            if len(values) >= 20:
                if len(result["wide_rows"]) < 30:
                    result["wide_rows"].append(row_info)

            elem.clear()

            if row_no >= MAX_ROWS_SCAN:
                break

        result["rows_seen"] = row_no
        result["ok"] = True

    except ET.ParseError as exc:
        result["parse_error"] = f"XML parse error: {exc}"
    except Exception as exc:
        result["parse_error"] = str(exc)

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"Wrote row preview to: {OUTPUT_FILE.resolve()}")
    print(f"OK: {result['ok']}")
    print(f"File size MB: {result['file_size_mb']}")
    print(f"Rows seen: {result['rows_seen']}")
    print(f"Preview rows: {len(result['preview_rows'])}")
    print(f"Candidate data rows: {len(result['candidate_data_rows'])}")
    print(f"Wide rows: {len(result['wide_rows'])}")

    if result["parse_error"]:
        print(f"Parse error: {result['parse_error']}")

    print("\nFirst preview rows:")
    for row in result["preview_rows"][:25]:
        print(
            f"Row {row['row_no']} | cells={row['cell_count']} | "
            f"non_empty={row['non_empty_count']} | numeric={row['numeric_count']} | "
            f"{row['first_cells']}"
        )

    print("\nCandidate data rows:")
    for row in result["candidate_data_rows"][:10]:
        print(
            f"Row {row['row_no']} | cells={row['cell_count']} | "
            f"non_empty={row['non_empty_count']} | numeric={row['numeric_count']} | "
            f"{row['first_cells']}"
        )


if __name__ == "__main__":
    main()