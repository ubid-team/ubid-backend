from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BusinessRecord(BaseModel):
    business_name: str = Field(..., min_length=1)
    address: str | None = None
    district: str | None = None
    pin_code: str | None = None
    phone: str | None = None
    pan_hash: str | None = None
    gstin_hash: str | None = None
    business_type: str | None = None
    business_category: str | None = None
    source: str | None = None
    uses_machinery: bool | None = None
    handles_food: bool | None = None
    pollution_category: str | None = None
    employees: int | None = None


class DataSourceSummary(BaseModel):
    logical_name: str
    file_name: str
    relative_path: str
    row_count: int
    columns: list[str]
    last_loaded_at: datetime


class DataSourcesResponse(BaseModel):
    data_loaded: bool
    source_count: int
    loaded_sources: list[DataSourceSummary]


class ReloadResponse(BaseModel):
    status: str
    data_loaded: bool
    source_count: int
    loaded_sources: list[DataSourceSummary]


class BusinessSearchResult(BaseModel):
    ubid: str | None = None
    source_record_id: str
    source: str
    business_name: str
    address: str | None = None
    district: str | None = None
    pin_code: str | None = None
    business_type: str | None = None
    business_category: str | None = None
    score: int
    raw: dict[str, Any] = Field(default_factory=dict)
