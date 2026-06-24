from pydantic import BaseModel


class CommLineMetadata(BaseModel):
    comm_line_num: int
    name: str | None = None


class DeviceMetadata(BaseModel):
    device_num: int
    name: str | None = None
    comm_line_num: int | None = None


class ChannelMetadata(BaseModel):
    cnl_num: int
    active: bool
    name: str | None = None
    tag_code: str | None = None

    device_num: int | None = None
    device_name: str | None = None

    comm_line_num: int | None = None
    comm_line_name: str | None = None

    cnl_type_id: int | None = None
    format_id: int | None = None
    unit_id: int | None = None


class ChannelsMetadataResponse(BaseModel):
    count: int
    channels: list[ChannelMetadata]


class DeviceChannelsSummary(BaseModel):
    device_num: int | None = None
    device_name: str | None = None
    channel_count: int
    active_channel_count: int


class CommLineChannelsSummary(BaseModel):
    comm_line_num: int | None = None
    comm_line_name: str | None = None
    channel_count: int
    active_channel_count: int


class MetadataSummaryResponse(BaseModel):
    total_channels: int
    active_channels: int
    inactive_channels: int
    device_count: int
    comm_line_count: int
    devices: list[DeviceChannelsSummary]
    comm_lines: list[CommLineChannelsSummary]