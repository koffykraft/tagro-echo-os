-- TAGRO ECHO OS operational twin source layer v0.5
-- Imported TAGRO/BUSY/Closing Cash/service/bank/history becomes queryable working material
-- inside the isolated ECHO Operational Twin. Source provenance remains explicit.

create table if not exists twin_source_sync_runs (
  sync_run_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  source_system text not null,
  source_locator text not null,
  source_class text not null,
  source_as_of timestamptz,
  started_at timestamptz not null,
  completed_at timestamptz,
  record_count integer not null default 0,
  inserted_count integer not null default 0,
  updated_count integer not null default 0,
  unchanged_count integer not null default 0,
  payload_hash text not null default '',
  status text not null default 'running',
  provenance_json text not null default '{}'
);

create index if not exists idx_twin_sync_enterprise_time
  on twin_source_sync_runs(enterprise_id, started_at desc);

create table if not exists twin_source_records (
  record_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  source_system text not null,
  source_locator text not null,
  source_class text not null,
  branch_code text not null default '',
  domain text not null,
  record_type text not null,
  source_record_id text not null,
  source_effective_at timestamptz,
  source_updated_at timestamptz,
  ingested_at timestamptz not null,
  content_hash text not null,
  payload_json text not null,
  provenance_json text not null default '{}',
  active boolean not null default true,
  unique(enterprise_id, source_system, source_locator, record_type, source_record_id)
);

create index if not exists idx_twin_source_domain_time
  on twin_source_records(enterprise_id, domain, source_effective_at desc);
create index if not exists idx_twin_source_branch_time
  on twin_source_records(enterprise_id, branch_code, source_effective_at desc);
create index if not exists idx_twin_source_type_time
  on twin_source_records(enterprise_id, record_type, source_effective_at desc);
create index if not exists idx_twin_source_system
  on twin_source_records(enterprise_id, source_system, source_locator);

create table if not exists twin_projection_checkpoints (
  checkpoint_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  projection_code text not null,
  source_sync_run_id text references twin_source_sync_runs(sync_run_id),
  source_effective_at timestamptz,
  projected_at timestamptz not null,
  result_json text not null default '{}',
  unique(enterprise_id, projection_code, source_sync_run_id)
);

create index if not exists idx_twin_projection_enterprise
  on twin_projection_checkpoints(enterprise_id, projection_code, projected_at desc);
