from __future__ import annotations

import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_XML_PATH = Path("scada_project/BaseXML/HistData.xml")
DEFAULT_DB_PATH = Path("data/scada_history.sqlite")

SOURCE_NAME = "histdata_xml"

BATCH_SIZE = int(os.getenv("IMPORT_BATCH_SIZE", "50000"))
MAX_DATA_ROWS = int(os.getenv("MAX_DATA_ROWS", "0"))  # 0 means unlimited


def strip_namespace(name: str) -> str:
    """Remove XML namespace from tag or attribute name."""
    if "}" in name:
        return name.split("}", 1)[1]

    return name


def get_attr_by_local_name(attrs: dict[str, str], local_name: str) -> str | None:
    """Get XML attribute by local name, ignoring namespace."""
    for key, value in attrs.items():
        if strip_namespace(key) == local_name:
            return value

    return None


def compact_text(text: str | None) -> str | None:
    """Normalize cell text."""
    if text is None:
        return None

    cleaned = re.sub(r"\s+", " ", text).strip()

    if not cleaned:
        return None

    return cleaned


def parse_row(row_elem: ET.Element) -> list[str | None]:
    """Parse one SpreadsheetML Row element into a list of cell values."""
    values: list[str | None] = []
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

        cell_value = None

        for child in cell:
            if strip_namespace(child.tag) == "Data":
                cell_value = compact_text(child.text)
                break

        values.append(cell_value)
        current_col += 1

    return values


def parse_channel_header(value: str | None) -> int | None:
    """Extract channel number from a header like 'Channel 101'."""
    if not value:
        return None

    match = re.search(r"Channel\s+(\d+)", value, flags=re.IGNORECASE)

    if not match:
        return None

    return int(match.group(1))


def parse_timestamp(value: str | None) -> str | None:
    """Parse Rapid SCADA exported timestamp and return ISO-like string."""
    if not value:
        return None

    text = value.strip()

    formats = [
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.isoformat(timespec="seconds")
        except ValueError:
            continue

    return None


def parse_number(value: str | None) -> float | None:
    """Parse exported numeric values with comma thousands and dot decimals."""
    if value is None:
        return None

    text = value.strip()

    if not text or text in {"---", "-", "NaN", "nan", "null", "NULL"}:
        return None

    # Remove common thousands separator.
    normalized = text.replace(",", "")

    try:
        return float(normalized)
    except ValueError:
        return None


def create_schema(conn: sqlite3.Connection) -> None:
    """Create local history schema."""
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        PRAGMA temp_store = MEMORY;

        DROP TABLE IF EXISTS history_values;
        DROP TABLE IF EXISTS history_import_channels;
        DROP TABLE IF EXISTS history_imports;

        CREATE TABLE history_values (
            cnl_num INTEGER NOT NULL,
            ts TEXT NOT NULL,
            val REAL,
            stat INTEGER,
            source TEXT NOT NULL
        );

        CREATE TABLE history_import_channels (
            column_index INTEGER NOT NULL,
            cnl_num INTEGER NOT NULL,
            header TEXT NOT NULL,
            source TEXT NOT NULL
        );

        CREATE TABLE history_imports (
            source TEXT PRIMARY KEY,
            xml_path TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            data_rows INTEGER NOT NULL,
            inserted_values INTEGER NOT NULL,
            skipped_values INTEGER NOT NULL,
            first_ts TEXT,
            last_ts TEXT
        );
        """
    )


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes after bulk import for better performance."""
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_history_values_cnl_ts
            ON history_values (cnl_num, ts);

        CREATE INDEX IF NOT EXISTS idx_history_values_ts
            ON history_values (ts);

        CREATE INDEX IF NOT EXISTS idx_history_values_cnl
            ON history_values (cnl_num);
        """
    )


def import_xml_to_sqlite(xml_path: Path, db_path: Path) -> None:
    """Import SpreadsheetML historical data into local SQLite."""
    start_time = time.time()

    if not xml_path.exists():
        raise FileNotFoundError(f"HistData.xml not found: {xml_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)

    try:
        create_schema(conn)

        header_channels: list[int | None] | None = None
        header_row_no: int | None = None

        data_rows = 0
        inserted_values = 0
        skipped_values = 0
        first_ts: str | None = None
        last_ts: str | None = None

        batch: list[tuple[int, str, float, None, str]] = []

        context = ET.iterparse(xml_path, events=("end",))

        row_no = 0

        for event, elem in context:
            if strip_namespace(elem.tag) != "Row":
                continue

            row_no += 1
            values = parse_row(elem)

            if not values:
                elem.clear()
                continue

            # Detect header row: Date and Time, Channel 101, Channel 102, ...
            if header_channels is None:
                first_cell = values[0]

                if first_cell and first_cell.strip().lower() == "date and time":
                    channels: list[int | None] = []

                    for cell_value in values[1:]:
                        channels.append(parse_channel_header(cell_value))

                    valid_channels = [cnl for cnl in channels if cnl is not None]

                    if valid_channels:
                        header_channels = channels
                        header_row_no = row_no

                        channel_rows = [
                            (
                                col_index + 2,
                                cnl_num,
                                values[col_index + 1] or "",
                                SOURCE_NAME,
                            )
                            for col_index, cnl_num in enumerate(header_channels)
                            if cnl_num is not None
                        ]

                        conn.executemany(
                            """
                            INSERT INTO history_import_channels
                                (column_index, cnl_num, header, source)
                            VALUES (?, ?, ?, ?)
                            """,
                            channel_rows,
                        )
                        conn.commit()

                        print(
                            f"Detected header row {header_row_no} "
                            f"with {len(valid_channels)} channels."
                        )

                elem.clear()
                continue

            ts = parse_timestamp(values[0])

            if ts is None:
                elem.clear()
                continue

            data_rows += 1

            if first_ts is None:
                first_ts = ts

            last_ts = ts

            for idx, cnl_num in enumerate(header_channels):
                if cnl_num is None:
                    continue

                value_index = idx + 1

                if value_index >= len(values):
                    skipped_values += 1
                    continue

                val = parse_number(values[value_index])

                if val is None:
                    skipped_values += 1
                    continue

                batch.append((cnl_num, ts, val, None, SOURCE_NAME))

                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        """
                        INSERT INTO history_values
                            (cnl_num, ts, val, stat, source)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    inserted_values += len(batch)
                    batch.clear()
                    conn.commit()

                    elapsed = time.time() - start_time
                    print(
                        f"Imported rows={data_rows:,} "
                        f"values={inserted_values:,} "
                        f"last_ts={last_ts} "
                        f"elapsed={elapsed:.1f}s"
                    )

            elem.clear()

            if MAX_DATA_ROWS and data_rows >= MAX_DATA_ROWS:
                print(f"Stopped early because MAX_DATA_ROWS={MAX_DATA_ROWS}.")
                break

        if header_channels is None:
            raise RuntimeError("Could not detect header row with channel numbers.")

        if batch:
            conn.executemany(
                """
                INSERT INTO history_values
                    (cnl_num, ts, val, stat, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                batch,
            )
            inserted_values += len(batch)
            batch.clear()
            conn.commit()

        print("Creating indexes...")
        create_indexes(conn)

        imported_at = datetime.now().isoformat(timespec="seconds")

        conn.execute(
            """
            INSERT INTO history_imports
                (
                    source,
                    xml_path,
                    imported_at,
                    data_rows,
                    inserted_values,
                    skipped_values,
                    first_ts,
                    last_ts
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                SOURCE_NAME,
                str(xml_path),
                imported_at,
                data_rows,
                inserted_values,
                skipped_values,
                first_ts,
                last_ts,
            ),
        )
        conn.commit()

        elapsed = time.time() - start_time

        print("")
        print("Import completed.")
        print(f"Database: {db_path.resolve()}")
        print(f"Header row: {header_row_no}")
        print(f"Data rows: {data_rows:,}")
        print(f"Inserted values: {inserted_values:,}")
        print(f"Skipped/null values: {skipped_values:,}")
        print(f"First timestamp: {first_ts}")
        print(f"Last timestamp: {last_ts}")
        print(f"Elapsed seconds: {elapsed:.1f}")

    finally:
        conn.close()


def main() -> None:
    """Script entrypoint."""
    xml_path = Path(os.getenv("HISTDATA_XML_PATH", str(DEFAULT_XML_PATH)))
    db_path = Path(os.getenv("SCADA_HISTORY_SQLITE_PATH", str(DEFAULT_DB_PATH)))

    import_xml_to_sqlite(xml_path, db_path)


if __name__ == "__main__":
    main()