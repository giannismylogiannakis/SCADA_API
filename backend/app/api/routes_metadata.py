import xml.etree.ElementTree as ET

from fastapi import APIRouter, HTTPException

from app.metadata.models import (
    ChannelMetadata,
    ChannelsMetadataResponse,
    CommLineChannelsSummary,
    DeviceChannelsSummary,
    MetadataSummaryResponse,
)
from app.metadata.xml_loader import load_channels_metadata


router = APIRouter(prefix="/api/metadata", tags=["metadata"])


def _load_channels_or_error() -> list[ChannelMetadata]:
    """Load channel metadata and convert loader errors to HTTP errors."""
    try:
        return load_channels_metadata()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ET.ParseError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid XML file: {exc}") from exc


@router.get("/summary", response_model=MetadataSummaryResponse)
def get_metadata_summary():
    """Return summary information for loaded Rapid SCADA metadata."""
    channels = _load_channels_or_error()

    active_channels = sum(1 for channel in channels if channel.active)
    inactive_channels = len(channels) - active_channels

    device_rows: dict[int | None, dict] = {}
    comm_line_rows: dict[int | None, dict] = {}

    for channel in channels:
        device_key = channel.device_num

        if device_key not in device_rows:
            device_rows[device_key] = {
                "device_num": channel.device_num,
                "device_name": channel.device_name,
                "channel_count": 0,
                "active_channel_count": 0,
            }

        device_rows[device_key]["channel_count"] += 1

        if channel.active:
            device_rows[device_key]["active_channel_count"] += 1

        comm_line_key = channel.comm_line_num

        if comm_line_key not in comm_line_rows:
            comm_line_rows[comm_line_key] = {
                "comm_line_num": channel.comm_line_num,
                "comm_line_name": channel.comm_line_name,
                "channel_count": 0,
                "active_channel_count": 0,
            }

        comm_line_rows[comm_line_key]["channel_count"] += 1

        if channel.active:
            comm_line_rows[comm_line_key]["active_channel_count"] += 1

    devices = [
        DeviceChannelsSummary(**row)
        for row in sorted(
            device_rows.values(),
            key=lambda row: (row["device_num"] is None, row["device_num"] or 0),
        )
    ]

    comm_lines = [
        CommLineChannelsSummary(**row)
        for row in sorted(
            comm_line_rows.values(),
            key=lambda row: (row["comm_line_num"] is None, row["comm_line_num"] or 0),
        )
    ]

    return MetadataSummaryResponse(
        total_channels=len(channels),
        active_channels=active_channels,
        inactive_channels=inactive_channels,
        device_count=len({channel.device_num for channel in channels if channel.device_num is not None}),
        comm_line_count=len({channel.comm_line_num for channel in channels if channel.comm_line_num is not None}),
        devices=devices,
        comm_lines=comm_lines,
    )


@router.get("/channels", response_model=ChannelsMetadataResponse)
def get_channels_metadata(active_only: bool = False):
    """Return Rapid SCADA channel metadata loaded from BaseXML files."""
    channels = _load_channels_or_error()

    if active_only:
        channels = [channel for channel in channels if channel.active]

    return ChannelsMetadataResponse(
        count=len(channels),
        channels=channels,
    )


@router.get("/channels/{cnl_num}", response_model=ChannelMetadata)
def get_channel_metadata(cnl_num: int):
    """Return metadata for one Rapid SCADA channel."""
    channels = _load_channels_or_error()

    for channel in channels:
        if channel.cnl_num == cnl_num:
            return channel

    raise HTTPException(
        status_code=404,
        detail=f"Channel not found: {cnl_num}",
    )