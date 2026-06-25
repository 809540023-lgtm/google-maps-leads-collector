create table if not exists google_maps_leads (
    id uuid primary key,
    payload jsonb not null,
    created_at timestamptz not null,
    updated_at timestamptz not null
);

create table if not exists google_maps_scrape_jobs (
    id uuid primary key,
    payload jsonb not null,
    created_at timestamptz not null,
    updated_at timestamptz not null
);

create index if not exists idx_google_maps_leads_updated_at
    on google_maps_leads (updated_at desc);

create index if not exists idx_google_maps_leads_phone
    on google_maps_leads ((payload ->> 'normalized_phone'));

create index if not exists idx_google_maps_leads_place_id
    on google_maps_leads ((payload ->> 'place_id'));

create index if not exists idx_google_maps_leads_grade
    on google_maps_leads ((payload ->> 'lead_grade'));

create index if not exists idx_google_maps_scrape_jobs_updated_at
    on google_maps_scrape_jobs (updated_at desc);

