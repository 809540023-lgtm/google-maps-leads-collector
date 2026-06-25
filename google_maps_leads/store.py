from __future__ import annotations

import csv
import io
import json
import os
import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from google_maps_leads.geocoding import bounding_box, geocode_address, haversine_distance_m, parse_coordinates
from google_maps_leads.repository import GoogleMapsLeadsJsonRepository, GoogleMapsLeadsPostgresRepository
from google_maps_leads.schemas import LeadCreate, LeadImportResult, LeadRecord, LeadUpdate, ScrapeJobCreate, ScrapeJobRecord


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "google_maps_leads_store.json"
DEFAULT_QUERY_TERMS = ["工廠", "公司", "倉儲", "物流", "辦公室", "汽車維修", "診所", "店家"]


def _now() -> datetime:
    return datetime.now().astimezone()


def _clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(_clean(item) for item in value if _clean(item))
    return str(value).strip()


def _float_or_none(value: object) -> float | None:
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int_or_none(value: object) -> int | None:
    number = _float_or_none(value)
    return int(number) if number is not None else None


def _split_tags(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,，#\n]+", value) if part.strip()]


def _split_terms(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,，\n]+", value) if part.strip()]


def _normalize_phone(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return ""
    if raw.startswith("+"):
        return f"+{digits}" if 10 <= len(digits) <= 15 else ""
    if digits.startswith("886"):
        return f"+{digits}" if 11 <= len(digits) <= 12 else ""
    if digits.startswith("09") and len(digits) == 10:
        return f"+886{digits[1:]}"
    if digits.startswith("0") and 9 <= len(digits) <= 10:
        return f"+886{digits[1:]}"
    return ""


def _distance_band(distance_m: float | None) -> str:
    if distance_m is None:
        return "unknown"
    if distance_m <= 1000:
        return "0-1km"
    if distance_m <= 3000:
        return "1-3km"
    if distance_m <= 5000:
        return "3-5km"
    return "5km+"


def _lead_grade(distance_m: float | None, phone: str, category: str) -> str:
    if distance_m is None:
        return "U"
    if distance_m <= 1000 and phone:
        return "A"
    if distance_m <= 3000 and phone:
        return "B"
    if distance_m <= 5000:
        return "C"
    return "D"


def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower() or "gmaps-results"


def _first_value(row: dict[str, Any], *keys: str) -> object:
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    for key in keys:
        if key.lower() in normalized and _clean(normalized[key.lower()]):
            return normalized[key.lower()]
    return ""


def _is_machine_location(value: str) -> bool:
    text = value.strip().lower()
    return bool(parse_coordinates(text)) or "://" in text or text.startswith("geo:")


def _center_lookup_text(payload: ScrapeJobCreate) -> str:
    return payload.address.strip() or payload.location.strip()


def _query_context(payload: ScrapeJobCreate) -> str:
    for candidate in (payload.location.strip(), payload.address.strip()):
        if candidate and not _is_machine_location(candidate):
            return candidate
    return ""


def _dedupe_key(lead: LeadRecord | LeadCreate) -> tuple[str, str, str]:
    phone_digits = re.sub(r"\D+", "", lead.phone)
    return (lead.place_id.strip().lower(), phone_digits, lead.name.strip().lower())


class GoogleMapsLeadsStore:
    def __init__(self, path: Path = DATA_PATH) -> None:
        backend = os.getenv("GOOGLE_MAPS_LEADS_STORAGE_BACKEND", "json").strip().lower()
        dsn = (
            os.getenv("GOOGLE_MAPS_LEADS_POSTGRES_DSN")
            or os.getenv("DATABASE_URL")
            or os.getenv("SCHOOL_PLATFORM_POSTGRES_DSN")
            or ""
        )
        if path == DATA_PATH and backend == "postgres" and dsn:
            self.repository = GoogleMapsLeadsPostgresRepository(dsn)
        else:
            self.repository = GoogleMapsLeadsJsonRepository(path)
        self.leads: list[LeadRecord] = []
        self.jobs: list[ScrapeJobRecord] = []
        self._load()

    def _load(self) -> None:
        payload = self.repository.read()
        self.leads = [LeadRecord.model_validate(item) for item in payload["leads"]]
        self.jobs = [ScrapeJobRecord.model_validate(item) for item in payload["jobs"]]

    def _save(self) -> None:
        self.repository.write(
            {
                "leads": [lead.model_dump(mode="json") for lead in self.leads],
                "jobs": [job.model_dump(mode="json") for job in self.jobs],
            }
        )

    def metrics(self) -> dict[str, int]:
        with_phone = sum(1 for lead in self.leads if lead.phone and lead.normalized_phone)
        with_email = sum(1 for lead in self.leads if lead.email)
        contacted = sum(1 for lead in self.leads if lead.status == "contacted")
        qualified = sum(1 for lead in self.leads if lead.status == "qualified")
        grade_a = sum(1 for lead in self.leads if lead.lead_grade == "A")
        grade_b = sum(1 for lead in self.leads if lead.lead_grade == "B")
        return {
            "total": len(self.leads),
            "with_phone": with_phone,
            "with_email": with_email,
            "contacted": contacted,
            "qualified": qualified,
            "grade_a": grade_a,
            "grade_b": grade_b,
            "jobs": len(self.jobs),
        }

    def list_leads(self, q: str = "", status: str = "", phone_only: bool = False) -> list[LeadRecord]:
        rows = sorted(self.leads, key=lambda item: item.updated_at, reverse=True)
        if q:
            needle = q.strip().lower()
            rows = [
                lead
                for lead in rows
                if needle in " ".join(
                    [
                        lead.name,
                        lead.phone,
                        lead.email,
                        lead.website,
                        lead.address,
                        lead.category,
                        lead.source_query,
                        lead.normalized_phone,
                        lead.distance_band,
                        lead.lead_grade,
                        " ".join(lead.tags),
                    ]
                ).lower()
            ]
        if status:
            rows = [lead for lead in rows if lead.status == status]
        if phone_only:
            rows = [lead for lead in rows if lead.phone and lead.normalized_phone]
        return rows

    def list_jobs(self) -> list[ScrapeJobRecord]:
        return sorted(self.jobs, key=lambda item: item.updated_at, reverse=True)

    def create_lead(self, payload: LeadCreate) -> LeadRecord:
        now = _now()
        payload = payload.model_copy(update={"normalized_phone": payload.normalized_phone or _normalize_phone(payload.phone)})
        lead = LeadRecord(id=uuid4(), created_at=now, updated_at=now, **payload.model_dump())
        existing = self._find_duplicate(lead)
        if existing:
            merged = self._merge_lead(existing, payload)
            self._save()
            return merged
        self.leads.append(lead)
        self._save()
        return lead

    def update_lead(self, lead_id: UUID, payload: LeadUpdate) -> LeadRecord | None:
        for index, lead in enumerate(self.leads):
            if lead.id == lead_id:
                changes = payload.model_dump(exclude_unset=True)
                updated = lead.model_copy(update={**changes, "updated_at": _now()})
                self.leads[index] = updated
                self._save()
                return updated
        return None

    def create_job(self, payload: ScrapeJobCreate) -> ScrapeJobRecord:
        now = _now()
        payload, geocode_source, geocode_status = self._prepare_job(payload)
        command = self.build_scraper_command(payload)
        job = ScrapeJobRecord(
            id=uuid4(),
            command=command,
            queries_text=self.build_queries_text(payload),
            grid_bbox=self.build_grid_bbox(payload),
            geocode_source=geocode_source,
            geocode_status=geocode_status,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        self.jobs.append(job)
        self._save()
        return job

    def mark_job_imported(self, job_id: UUID, count: int) -> None:
        for index, job in enumerate(self.jobs):
            if job.id == job_id:
                imported_count = sum(1 for lead in self.leads if lead.source_job_id == job_id) or count
                self.jobs[index] = job.model_copy(
                    update={"status": "imported", "imported_count": imported_count, "updated_at": _now()}
                )
                self._save()
                return

    def import_csv(self, raw: bytes, source_query: str = "", job_id: UUID | None = None) -> LeadImportResult:
        text = raw.decode("utf-8-sig", errors="ignore")
        rows = list(csv.DictReader(io.StringIO(text)))
        return self.import_rows(rows, source_query=source_query, job_id=job_id)

    def import_json(self, raw: bytes, source_query: str = "", job_id: UUID | None = None) -> LeadImportResult:
        text = raw.decode("utf-8-sig", errors="ignore").strip()
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows = payload.get("results") or payload.get("leads") or payload.get("data") or []
            else:
                rows = payload
        except json.JSONDecodeError:
            rows = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
        if not isinstance(rows, list):
            rows = []
        return self.import_rows([row for row in rows if isinstance(row, dict)], source_query=source_query, job_id=job_id)

    def import_rows(
        self,
        rows: list[dict[str, Any]],
        source_query: str = "",
        job_id: UUID | None = None,
    ) -> LeadImportResult:
        imported = 0
        updated = 0
        skipped = 0
        filtered_out = 0
        job = self._job_by_id(job_id) if job_id else None
        for row in rows:
            lead = self._lead_from_row(row, source_query)
            if not lead.name:
                skipped += 1
                continue
            lead = self._enrich_lead_for_job(lead, job)
            if self._should_filter_for_job(lead, job):
                filtered_out += 1
                continue
            existing = self._find_duplicate(lead)
            if existing:
                self._merge_lead(existing, lead)
                updated += 1
            else:
                now = _now()
                self.leads.append(LeadRecord(id=uuid4(), created_at=now, updated_at=now, **lead.model_dump()))
                imported += 1
        if job_id:
            self.mark_job_imported(job_id, imported + updated)
        self._save()
        return LeadImportResult(
            imported=imported,
            updated=updated,
            skipped=skipped,
            filtered_out=filtered_out,
            total=len(rows),
        )

    def export_csv(self, rows: list[LeadRecord]) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "name",
                "phone",
                "normalized_phone",
                "email",
                "website",
                "address",
                "category",
                "rating",
                "reviews",
                "distance_m",
                "distance_band",
                "lead_grade",
                "source_query",
                "source_job_id",
                "status",
                "tags",
                "notes",
                "google_maps_url",
                "place_id",
                "latitude",
                "longitude",
            ],
        )
        writer.writeheader()
        for lead in rows:
            writer.writerow(
                {
                    "name": lead.name,
                    "phone": lead.phone,
                    "normalized_phone": lead.normalized_phone,
                    "email": lead.email,
                    "website": lead.website,
                    "address": lead.address,
                    "category": lead.category,
                    "rating": lead.rating or "",
                    "reviews": lead.reviews or "",
                    "distance_m": round(lead.distance_m, 1) if lead.distance_m is not None else "",
                    "distance_band": lead.distance_band,
                    "lead_grade": lead.lead_grade,
                    "source_query": lead.source_query,
                    "source_job_id": lead.source_job_id or "",
                    "status": lead.status,
                    "tags": ", ".join(lead.tags),
                    "notes": lead.notes,
                    "google_maps_url": lead.google_maps_url,
                    "place_id": lead.place_id,
                    "latitude": lead.latitude or "",
                    "longitude": lead.longitude or "",
                }
            )
        return output.getvalue()

    def build_scraper_command(self, payload: ScrapeJobCreate) -> str:
        query = f"{payload.query} {payload.location or payload.address}".strip()
        queries_text = self.build_queries_text(payload)
        flags = [
            "-json",
            "-lang",
            payload.lang,
            "-depth",
            str(payload.depth),
            "-c",
            str(payload.concurrency),
            "-exit-on-inactivity",
            "5m",
        ]
        if payload.search_mode == "radius" and payload.center_latitude is not None and payload.center_longitude is not None:
            flags.extend(
                [
                    "-geo",
                    f"{payload.center_latitude:.6f},{payload.center_longitude:.6f}",
                    "-radius",
                    str(payload.radius_m),
                    "-zoom",
                    str(payload.zoom),
                ]
            )
        elif payload.search_mode == "grid" and payload.center_latitude is not None and payload.center_longitude is not None:
            flags.extend(
                [
                    "-grid-bbox",
                    self.build_grid_bbox(payload),
                    "-grid-cell",
                    str(payload.grid_cell_km),
                    "-zoom",
                    str(payload.zoom),
                ]
            )
        if payload.extract_email:
            flags.append("-email")
        result_name = _safe_filename(query)
        quoted_flags = " ".join(shlex.quote(item) for item in flags)
        return (
            "mkdir -p gmaps-output && "
            "cat > gmaps-output/queries.txt <<'EOF'\n"
            f"{queries_text}\n"
            "EOF\n"
            "docker run --rm "
            "-v gmaps-playwright-cache:/opt "
            '-v "$PWD/gmaps-output/queries.txt:/queries.txt:ro" '
            '-v "$PWD/gmaps-output:/out" '
            "gosom/google-maps-scraper "
            "-input /queries.txt "
            f"-results /out/{result_name}.json "
            f"{quoted_flags}"
        )

    def build_local_binary_command(self, payload: ScrapeJobCreate) -> str:
        query = f"{payload.query} {payload.location or payload.address}".strip()
        flags = [
            "-json",
            "-input",
            "gmaps-output/queries.txt",
            "-results",
            f"gmaps-output/{_safe_filename(query)}.json",
            "-lang",
            payload.lang,
            "-depth",
            str(payload.depth),
            "-c",
            str(payload.concurrency),
            "-exit-on-inactivity",
            "5m",
        ]
        if payload.search_mode == "radius" and payload.center_latitude is not None and payload.center_longitude is not None:
            flags.extend(
                [
                    "-geo",
                    f"{payload.center_latitude:.6f},{payload.center_longitude:.6f}",
                    "-radius",
                    str(payload.radius_m),
                    "-zoom",
                    str(payload.zoom),
                ]
            )
        elif payload.search_mode == "grid" and payload.center_latitude is not None and payload.center_longitude is not None:
            flags.extend(
                [
                    "-grid-bbox",
                    self.build_grid_bbox(payload),
                    "-grid-cell",
                    str(payload.grid_cell_km),
                    "-zoom",
                    str(payload.zoom),
                ]
            )
        if payload.extract_email:
            flags.append("-email")
        return "./google-maps-scraper " + " ".join(shlex.quote(item) for item in flags)

    def build_queries_text(self, payload: ScrapeJobCreate) -> str:
        terms = payload.query_terms or _split_terms(payload.query) or DEFAULT_QUERY_TERMS
        context = _query_context(payload)
        lines = [f"{term} {context}".strip() for term in terms]
        return "\n".join(dict.fromkeys(line for line in lines if line))

    def build_grid_bbox(self, payload: ScrapeJobCreate) -> str:
        if payload.center_latitude is None or payload.center_longitude is None:
            return ""
        min_lat, min_lon, max_lat, max_lon = bounding_box(
            payload.center_latitude,
            payload.center_longitude,
            payload.max_distance_m or payload.radius_m,
        )
        return f"{min_lat},{min_lon},{max_lat},{max_lon}"

    def _prepare_job(self, payload: ScrapeJobCreate) -> tuple[ScrapeJobCreate, str, str]:
        terms = payload.query_terms or _split_terms(payload.query) or DEFAULT_QUERY_TERMS
        updates: dict[str, object] = {"query_terms": terms}
        geocode_source = ""
        geocode_status = "not_needed"
        needs_coordinates = payload.search_mode in {"radius", "grid"}
        if needs_coordinates and (payload.center_latitude is None or payload.center_longitude is None):
            result = geocode_address(_center_lookup_text(payload))
            if result:
                updates["center_latitude"] = result.latitude
                updates["center_longitude"] = result.longitude
                updates["geocoded_address"] = result.formatted_address
                geocode_source = result.source
                geocode_status = "ok"
            else:
                updates["search_mode"] = "simple"
                geocode_status = "failed_fallback_to_simple"
        elif needs_coordinates:
            geocode_source = "manual"
            geocode_status = "provided"
            updates["geocoded_address"] = payload.geocoded_address or _center_lookup_text(payload)
        return payload.model_copy(update=updates), geocode_source, geocode_status

    def _lead_from_row(self, row: dict[str, Any], source_query: str) -> LeadCreate:
        raw_phone = _clean(
            _first_value(
                row,
                "phone",
                "phone_number",
                "telephone",
                "tel",
                "phones",
                "complete_phone",
                "international_phone_number",
            )
        )
        normalized_phone = _normalize_phone(raw_phone)
        if not normalized_phone:
            raw_phone = ""
        business_status = _clean(_first_value(row, "business_status", "status", "descriptions", "description"))
        return LeadCreate(
            source_query=source_query or _clean(_first_value(row, "query", "source_query", "search", "input_id")),
            name=_clean(_first_value(row, "name", "title", "business_name", "place_name")),
            phone=raw_phone,
            normalized_phone=normalized_phone,
            email=_clean(_first_value(row, "email", "emails", "mail")),
            website=_clean(_first_value(row, "website", "site", "url", "domain")),
            address=_clean(_first_value(row, "address", "complete_address", "full_address", "street")),
            category=_clean(_first_value(row, "category", "categories", "type")),
            rating=_float_or_none(_first_value(row, "rating", "review_rating", "stars")),
            reviews=_int_or_none(_first_value(row, "reviews", "review_count", "reviews_count", "ratings")),
            latitude=_float_or_none(_first_value(row, "latitude", "lat")),
            longitude=_float_or_none(_first_value(row, "longitude", "lng", "lon")),
            place_id=_clean(_first_value(row, "place_id", "cid", "google_id", "data_id")),
            google_maps_url=_clean(_first_value(row, "google_maps_url", "maps_url", "link", "google_url")),
            tags=_split_tags(_clean(_first_value(row, "tags", "categories"))),
            notes=business_status,
        )

    def _job_by_id(self, job_id: UUID | None) -> ScrapeJobRecord | None:
        if not job_id:
            return None
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def _enrich_lead_for_job(self, lead: LeadCreate, job: ScrapeJobRecord | None) -> LeadCreate:
        updates: dict[str, object] = {"normalized_phone": lead.normalized_phone or _normalize_phone(lead.phone)}
        if job:
            updates["source_job_id"] = job.id
            if not lead.source_query:
                updates["source_query"] = job.query
        if (
            job
            and job.center_latitude is not None
            and job.center_longitude is not None
            and lead.latitude is not None
            and lead.longitude is not None
        ):
            distance_m = haversine_distance_m(job.center_latitude, job.center_longitude, lead.latitude, lead.longitude)
            updates["distance_m"] = round(distance_m, 2)
            updates["distance_band"] = _distance_band(distance_m)
            updates["lead_grade"] = _lead_grade(distance_m, lead.phone, lead.category)
        elif not lead.lead_grade:
            updates["distance_band"] = lead.distance_band or "unknown"
            updates["lead_grade"] = _lead_grade(None, lead.phone, lead.category)
        return lead.model_copy(update=updates)

    def _should_filter_for_job(self, lead: LeadCreate, job: ScrapeJobRecord | None) -> bool:
        if not job or not job.strict_distance_filter:
            return False
        if lead.distance_m is None:
            return False
        return lead.distance_m > job.max_distance_m

    def _find_duplicate(self, lead: LeadRecord | LeadCreate) -> LeadRecord | None:
        target_place_id, target_phone, target_name = _dedupe_key(lead)
        for existing in self.leads:
            place_id, phone, name = _dedupe_key(existing)
            if target_place_id and place_id == target_place_id:
                return existing
            if target_phone and phone == target_phone and target_name == name:
                return existing
            if target_name and name == target_name and existing.address and lead.address and existing.address == lead.address:
                return existing
        return None

    def _merge_lead(self, existing: LeadRecord, incoming: LeadCreate) -> LeadRecord:
        index = self.leads.index(existing)
        data = existing.model_dump()
        incoming_data = incoming.model_dump()
        for key, value in incoming_data.items():
            if key == "tags":
                data["tags"] = sorted({*existing.tags, *incoming.tags})
            elif key == "notes":
                if incoming.notes and incoming.notes not in existing.notes:
                    data["notes"] = "\n".join(part for part in [existing.notes, incoming.notes] if part)
            elif value not in ("", None, []) and not data.get(key):
                data[key] = value
        data["updated_at"] = _now()
        merged = LeadRecord.model_validate(data)
        self.leads[index] = merged
        return merged
