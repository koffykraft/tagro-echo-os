-- TAGRO ECHO OS governed import observation / reconciliation layer v0.2.3
-- Migration evidence is not canonical truth. Sources are preserved as observations,
-- reconciled into candidates, and only explicitly accepted candidates may project
-- into canonical operational state.

create table import_sources (
  source_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  source_system text not null,
  source_locator text not null,
  source_as_of timestamptz,
  captured_at timestamptz not null,
  source_class text not null,
  immutable_ref text not null default '',
  notes text not null default '',
  unique(enterprise_id, source_system, source_locator, captured_at)
);

create table import_observations (
  observation_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  source_id text not null references import_sources(source_id),
  subject_kind text not null,
  source_subject_ref text not null,
  dimension_code text not null,
  observed_value_json text not null,
  observed_at timestamptz,
  confidence numeric(6,5),
  acceptance_state text not null default 'raw_supporting',
  provenance_ref text not null default '',
  created_at timestamptz not null,
  check(acceptance_state in ('raw_supporting','reviewed_provisional','accepted_supporting','rejected')),
  unique(enterprise_id, source_id, subject_kind, source_subject_ref, dimension_code)
);

create index idx_import_observations_subject
  on import_observations(enterprise_id, subject_kind, source_subject_ref);

create table reconciliation_candidates (
  candidate_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  subject_kind text not null,
  canonical_subject_ref text not null default '',
  candidate_key text not null,
  candidate_value_json text not null,
  status text not null default 'waiting',
  confidence numeric(6,5),
  evidence_json text not null default '[]',
  conflict_json text not null default '[]',
  decision_reason text not null default '',
  created_at timestamptz not null,
  decided_at timestamptz,
  decided_by_principal_id text references principals(principal_id),
  check(status in ('waiting','eligible','accepted','rejected','superseded')),
  unique(enterprise_id, subject_kind, candidate_key, status)
);

create index idx_reconciliation_candidates_waiting
  on reconciliation_candidates(enterprise_id, subject_kind, status, created_at);

create table canonical_admissions (
  admission_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  candidate_id text not null references reconciliation_candidates(candidate_id),
  canonical_table text not null,
  canonical_record_id text not null,
  admitted_at timestamptz not null,
  admitted_by_principal_id text not null references principals(principal_id),
  authority_basis text not null,
  evidence_json text not null,
  unique(enterprise_id, canonical_table, canonical_record_id, candidate_id)
);

-- Observation presence never grants canonical authority.
-- A receiver may inspect matching spectral dimensions, but only an accepted
-- reconciliation candidate plus authorised admission can mutate canonical state.
