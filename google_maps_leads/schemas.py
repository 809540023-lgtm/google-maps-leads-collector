from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LeadCreate(BaseModel):
    source_query: str = ""
    source_job_id: UUID | None = None
    name: str
    phone: str = ""
    normalized_phone: str = ""
    email: str = ""
    website: str = ""
    address: str = ""
    category: str = ""
    rating: float | None = None
    reviews: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    distance_m: float | None = None
    distance_band: str = ""
    lead_grade: str = ""
    place_id: str = ""
    google_maps_url: str = ""
    status: str = "new"
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


class LeadUpdate(BaseModel):
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class LeadRecord(LeadCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ScrapeJobCreate(BaseModel):
    query: str
    location: str = ""
    address: str = ""
    search_mode: str = "radius"
    query_terms: list[str] = Field(default_factory=list)
    center_latitude: float | None = None
    center_longitude: float | None = None
    radius_m: int = 3000
    max_distance_m: int = 5000
    grid_cell_km: float = 0.4
    zoom: int = 16
    lang: str = "zh-TW"
    concurrency: int = 4
    max_results: int = 50
    depth: int = 1
    extract_email: bool = False
    strict_distance_filter: bool = True
    geocoded_address: str = ""
    status: str = "planned"
    notes: str = ""


class ScrapeJobRecord(ScrapeJobCreate):
    id: UUID
    command: str
    queries_text: str = ""
    grid_bbox: str = ""
    geocode_source: str = ""
    geocode_status: str = ""
    created_at: datetime
    updated_at: datetime
    imported_count: int = 0


class LeadImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int
    filtered_out: int = 0
    total: int


class FacebookGroupCandidateInput(BaseModel):
    group_name: str
    region: str = ""
    group_type: str = ""
    member_count: int = 0
    post_activity: str = "unknown"
    latest_post_recency_days: int | None = None
    commercial_post_tolerance: str = "unknown"
    ads_allowed: str = "unknown"
    post_requires_review: str = "unknown"
    join_difficulty: str = "unknown"
    target_fit: str = "unknown"
    notes: str = ""


class FacebookAgentPlanRequest(BaseModel):
    region: str
    industry: str
    store_type: str = ""
    target_audience: str = ""
    offer: str = ""
    line_official_account: str = ""
    business_name: str = ""
    candidate_groups: list[FacebookGroupCandidateInput] = Field(default_factory=list)
