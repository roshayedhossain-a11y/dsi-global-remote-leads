create table if not exists public.leads (
  job_url text primary key,
  date_added date not null default current_date,
  company_name text,
  company_website text,
  job_title text,
  remote_type text,
  location_tag text,
  tech_tags text,
  date_posted text,
  source text,
  hq_region text,
  lead_status text default 'New Lead',
  priority text,
  linkedin_url text,
  contact_name text,
  contact_email text,
  eligibility text,
  eligibility_confidence integer,
  eligibility_evidence text,
  notes text,
  raw_json jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.source_runs (
  id bigserial primary key,
  run_time timestamptz not null default now(),
  source text not null,
  jobs_returned integer not null default 0,
  status text not null,
  message text,
  duration_ms integer
);

create index if not exists leads_company_idx on public.leads (company_name);
create index if not exists leads_date_added_idx on public.leads (date_added);
create index if not exists leads_source_idx on public.leads (source);
