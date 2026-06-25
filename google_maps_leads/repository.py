from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GoogleMapsLeadsJsonRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"leads": [], "jobs": []}
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return {"leads": [], "jobs": []}
        return {
            "leads": payload.get("leads") if isinstance(payload.get("leads"), list) else [],
            "jobs": payload.get("jobs") if isinstance(payload.get("jobs"), list) else [],
        }

    def write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
        temp_path.replace(self.path)


class GoogleMapsLeadsPostgresRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        import psycopg

        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                create table if not exists google_maps_leads (
                    id uuid primary key,
                    payload jsonb not null,
                    created_at timestamptz not null,
                    updated_at timestamptz not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists google_maps_scrape_jobs (
                    id uuid primary key,
                    payload jsonb not null,
                    created_at timestamptz not null,
                    updated_at timestamptz not null
                )
                """
            )
            conn.execute(
                "create index if not exists idx_google_maps_leads_updated_at on google_maps_leads (updated_at desc)"
            )
            conn.execute(
                "create index if not exists idx_google_maps_scrape_jobs_updated_at on google_maps_scrape_jobs (updated_at desc)"
            )

    def read(self) -> dict[str, Any]:
        import psycopg

        with psycopg.connect(self.dsn) as conn:
            lead_rows = conn.execute("select payload from google_maps_leads order by updated_at desc").fetchall()
            job_rows = conn.execute("select payload from google_maps_scrape_jobs order by updated_at desc").fetchall()
        return {
            "leads": [row[0] for row in lead_rows],
            "jobs": [row[0] for row in job_rows],
        }

    def write(self, payload: dict[str, Any]) -> None:
        import psycopg
        from psycopg.types.json import Jsonb

        leads = payload.get("leads") if isinstance(payload.get("leads"), list) else []
        jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else []
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                for lead in leads:
                    cursor.execute(
                        """
                        insert into google_maps_leads (id, payload, created_at, updated_at)
                        values (%s, %s, %s, %s)
                        on conflict (id) do update
                        set payload = excluded.payload,
                            updated_at = excluded.updated_at
                        """,
                        (lead["id"], Jsonb(lead), lead["created_at"], lead["updated_at"]),
                    )
                for job in jobs:
                    cursor.execute(
                        """
                        insert into google_maps_scrape_jobs (id, payload, created_at, updated_at)
                        values (%s, %s, %s, %s)
                        on conflict (id) do update
                        set payload = excluded.payload,
                            updated_at = excluded.updated_at
                        """,
                        (job["id"], Jsonb(job), job["created_at"], job["updated_at"]),
                    )
