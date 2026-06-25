from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_XML_PATH = Path("scada_project/BaseXML/HistData.xml")
OUTPUT_FILE = Path("histdata_xml_discovery.json")

MAX_END_ELEMENTS = int(os.getenv("MAX_END_ELEMENTS", "5000"))
MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", "100"))
MAX_TEXT_PREVIEW = 300
MAX_HEAD_BYTES = 20000


INTERESTING_WORDS = [
    "cnl",
    "channel",
    "num",
    "time",
    "timestamp",
    "date",
    "val",
    "value",
    "stat",
    "status",
    "trend",
    "data",
]


def strip_namespace(tag: str) -> str:
    """Remove XML namespace from a tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def compact_text(text: str | None) -> str | None:
    """Return a compact text preview."""
    if text is None:
        return None

    cleaned = re.sub(r"\s+", " ", text).strip()

    if not cleaned:
        return None

    return cleaned[:MAX_TEXT_PREVIEW]


def looks_interesting(tag: str, attrs: dict[str, str], text: str | None) -> bool:
    """Detect elements that may contain time/channel/value/status data."""
    blob = " ".join(
        [
            tag,
            " ".join(attrs.keys()),
            " ".join(str(value) for value in attrs.values()),
            text or "",
        ]
    ).lower()

    return any(word in blob for word in INTERESTING_WORDS)


def read_head_sample(path: Path) -> str:
    """Read the first bytes of a large XML file safely."""
    data = path.read_bytes()[:MAX_HEAD_BYTES]

    for encoding in ("utf-8-sig", "utf-8", "windows-1253", "latin-1"):
        try:
            return data.decode(encoding, errors="replace")
        except Exception:
            continue

    return data.decode("utf-8", errors="replace")


def main() -> None:
    """Inspect a large Rapid SCADA XML export without loading it into memory."""
    xml_path = Path(os.getenv("HISTDATA_XML_PATH", str(DEFAULT_XML_PATH)))

    result: dict[str, Any] = {
        "ok": False,
        "mode": "histdata_xml_streaming_discovery",
        "xml_path": str(xml_path),
        "file_exists": xml_path.exists(),
        "file_size_mb": None,
        "max_end_elements": MAX_END_ELEMENTS,
        "root": None,
        "root_attrs": {},
        "head_sample": None,
        "top_tags": [],
        "attributes_by_tag": {},
        "sample_elements": [],
        "candidate_elements": [],
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
    result["head_sample"] = read_head_sample(xml_path)

    tag_counts: Counter[str] = Counter()
    attrs_by_tag: dict[str, set[str]] = defaultdict(set)

    end_count = 0
    root_seen = False

    try:
        context = ET.iterparse(xml_path, events=("start", "end"))

        for event, elem in context:
            tag = strip_namespace(elem.tag)

            if event == "start" and not root_seen:
                result["root"] = tag
                result["root_attrs"] = dict(elem.attrib)
                root_seen = True

            if event != "end":
                continue

            end_count += 1
            tag_counts[tag] += 1

            attrs = dict(elem.attrib)

            for attr_name in attrs.keys():
                attrs_by_tag[tag].add(attr_name)

            text_preview = compact_text(elem.text)

            element_sample = {
                "tag": tag,
                "attrs": attrs,
                "text": text_preview,
            }

            if len(result["sample_elements"]) < MAX_SAMPLES and (attrs or text_preview):
                result["sample_elements"].append(element_sample)

            if (
                len(result["candidate_elements"]) < MAX_SAMPLES
                and looks_interesting(tag, attrs, text_preview)
            ):
                result["candidate_elements"].append(element_sample)

            elem.clear()

            if end_count >= MAX_END_ELEMENTS:
                break

        result["top_tags"] = [
            {"tag": tag, "count_seen": count}
            for tag, count in tag_counts.most_common(100)
        ]

        result["attributes_by_tag"] = {
            tag: sorted(attr_names)
            for tag, attr_names in sorted(attrs_by_tag.items())
        }

        result["ok"] = True

    except ET.ParseError as exc:
        result["parse_error"] = f"XML parse error: {exc}"
    except Exception as exc:
        result["parse_error"] = str(exc)

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"Wrote discovery output to: {OUTPUT_FILE.resolve()}")
    print(f"OK: {result['ok']}")
    print(f"File size MB: {result['file_size_mb']}")
    print(f"Root: {result['root']}")
    print(f"Top tags seen: {len(result['top_tags'])}")
    print(f"Candidate elements: {len(result['candidate_elements'])}")

    if result["parse_error"]:
        print(f"Parse error: {result['parse_error']}")

    print("\nTop tags:")
    for item in result["top_tags"][:20]:
        print(f"- {item['tag']}: {item['count_seen']}")

    print("\nCandidate elements:")
    for item in result["candidate_elements"][:10]:
        print(json.dumps(item, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()