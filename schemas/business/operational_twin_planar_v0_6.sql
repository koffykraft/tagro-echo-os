-- TAGRO ECHO OS Operational Twin Planar layer v0.6
-- Preserves the existing TAGRO AWS OS warehouse decomposition inside PostgreSQL.
-- Imported history remains provenance-labelled and distinct from ECHO-generated events.

create table if not exists twin_planar_entities (
  enterprise_id text not null references enterprises(enterprise_id),
  entity_id text not null,
  entity_type text not null,
  canonical_name text not null default '',
  branch_code text not null default '',
  attributes_json text not null default '{}',
  confidence numeric(6,5),
  source_sync_run_id text references twin_source_sync_runs(sync_run_id),
  source_updated_at timestamptz,
  ingested_at timestamptz not null default now(),
  primary key(enterprise_id, entity_id)
);

create index if not exists idx_twin_planar_entities_type_name
  on twin_planar_entities(enterprise_id, entity_type, canonical_name);
create index if not exists idx_twin_planar_entities_branch
  on twin_planar_entities(enterprise_id, branch_code, entity_type);

create table if not exists twin_planar_events (
  enterprise_id text not null references enterprises(enterprise_id),
  event_id text not null,
  event_type text not null,
  event_date date,
  branch_code text not null default '',
  amount numeric(18,4),
  summary text not null default '',
  attributes_json text not null default '{}',
  confidence numeric(6,5),
  source_sync_run_id text references twin_source_sync_runs(sync_run_id),
  source_effective_at timestamptz,
  source_updated_at timestamptz,
  ingested_at timestamptz not null default now(),
  primary key(enterprise_id, event_id)
);

create index if not exists idx_twin_planar_events_date
  on twin_planar_events(enterprise_id, event_date desc);
create index if not exists idx_twin_planar_events_branch_date
  on twin_planar_events(enterprise_id, branch_code, event_date desc);
create index if not exists idx_twin_planar_events_type_date
  on twin_planar_events(enterprise_id, event_type, event_date desc);

create table if not exists twin_planar_event_entities (
  enterprise_id text not null references enterprises(enterprise_id),
  event_id text not null,
  entity_id text not null,
  role text not null,
  source_sync_run_id text references twin_source_sync_runs(sync_run_id),
  ingested_at timestamptz not null default now(),
  primary key(enterprise_id, event_id, entity_id, role)
);

create index if not exists idx_twin_planar_event_entities_entity
  on twin_planar_event_entities(enterprise_id, entity_id, event_id);

create table if not exists twin_planar_evidence (
  enterprise_id text not null references enterprises(enterprise_id),
  evidence_id text not null,
  event_id text not null,
  source_domain text not null,
  source_database text not null default '',
  source_record_id text not null default '',
  source_path text not null default '',
  evidence_json text not null default '{}',
  source_sha256 text not null default '',
  source_sync_run_id text references twin_source_sync_runs(sync_run_id),
  ingested_at timestamptz not null default now(),
  primary key(enterprise_id, evidence_id)
);

create index if not exists idx_twin_planar_evidence_event
  on twin_planar_evidence(enterprise_id, event_id);
create index if not exists idx_twin_planar_evidence_domain
  on twin_planar_evidence(enterprise_id, source_domain, event_id);

create table if not exists twin_planar_relationships (
  enterprise_id text not null references enterprises(enterprise_id),
  relationship_id text not null,
  from_entity_id text not null,
  to_entity_id text not null,
  relationship_type text not null,
  start_date date,
  end_date date,
  evidence_id text not null default '',
  confidence numeric(6,5),
  source_sync_run_id text references twin_source_sync_runs(sync_run_id),
  ingested_at timestamptz not null default now(),
  primary key(enterprise_id, relationship_id)
);

create index if not exists idx_twin_planar_relationships_from
  on twin_planar_relationships(enterprise_id, from_entity_id, relationship_type);
create index if not exists idx_twin_planar_relationships_to
  on twin_planar_relationships(enterprise_id, to_entity_id, relationship_type);

create table if not exists twin_planar_projection_state (
  enterprise_id text not null references enterprises(enterprise_id),
  projection_code text not null,
  last_sync_run_id text references twin_source_sync_runs(sync_run_id),
  last_source_as_of timestamptz,
  updated_at timestamptz not null default now(),
  status text not null default 'ready',
  details_json text not null default '{}',
  primary key(enterprise_id, projection_code)
);

create or replace view twin_planar_event_read as
select
  e.enterprise_id,
  e.event_id,
  e.event_type,
  e.event_date,
  e.branch_code,
  e.amount,
  e.summary,
  e.attributes_json,
  e.confidence,
  e.source_sync_run_id,
  e.source_effective_at,
  e.ingested_at,
  coalesce(ev.evidence_count,0) as evidence_count,
  coalesce(en.entity_count,0) as entity_count
from twin_planar_events e
left join (
  select enterprise_id,event_id,count(*) evidence_count
  from twin_planar_evidence
  group by enterprise_id,event_id
) ev on ev.enterprise_id=e.enterprise_id and ev.event_id=e.event_id
left join (
  select enterprise_id,event_id,count(*) entity_count
  from twin_planar_event_entities
  group by enterprise_id,event_id
) en on en.enterprise_id=e.enterprise_id and en.event_id=e.event_id;
