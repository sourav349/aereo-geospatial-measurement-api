"""Typed API response contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class FileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_format: str
    crs: str
    feature_count: int
    status: Literal["COMPLETED"]
    created_at: datetime


class Measurement(BaseModel):
    status: Literal["MEASURED", "NOT_APPLICABLE", "UNSUPPORTED"]
    type: str | None
    value: float | None
    unit: str | None
    projected_crs: str | None
    message: str | None


class FeatureInfo(BaseModel):
    feature_index: int
    feature_id: str | None
    geometry_type: str
    geometry: dict[str, Any] | None
    crs: str
    properties: dict[str, Any]
    measurement: Measurement


class MeasurementsResponse(BaseModel):
    file_id: str
    total: int
    offset: int
    limit: int
    measurements: list[FeatureInfo]
