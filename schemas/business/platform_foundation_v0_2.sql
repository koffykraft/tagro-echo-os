-- TAGRO ECHO OS platform foundation v0.2
-- SaaS-safe ownership, identity, entitlement, event-potential and selective-propagation primitives.
-- Admitted for controlled NonProd migration only through the migration manifest.

create table enterprises (
  enterprise_id text primary key,
  code text not null unique,
  name text not null,
  status text not null default 'active',
  created_at timestamptz not null,
  data_residency_region text not null default 'ap-south-1'
);

create table principals (
  principal_id text primary key,
  principal_type text not null check(principal_type in ('human','system','service','ai_agent')),
  display_name text not null,
  external_identity_ref text not null default '',
  active boolean not null default true,
  created_at timestamptz not null
);

create table enterprise_memberships (
  membership_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  principal_id text not null references principals(principal_id),
  role_code text not null,
  tool_pack_code text not null default '',
  status text not null default 'active',
  valid_from timestamptz not null,
  valid_to timestamptz,
  unique(enterprise_id, principal_id, role_code)
);

create table capabilities (
  capability_code text primary key,
  name text not null,
  capability_class text not null,
  description text not null default '',
  active boolean not null default true
);

create table enterprise_entitlements (
  entitlement_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  capability_code text not null references capabilities(capability_code),
  status text not null check(status in ('enabled','disabled','suspended','archived')),
  effective_from timestamptz not null,
  effective_to timestamptz,
  configuration_json text not null default '{}',
  unique(enterprise_id, capability_code, effective_from)
);

create table echo_events (
  event_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  event_type text not null,
  subject_type text not null,
  subject_id text not null,
  occurred_at timestamptz not null,
  recorded_at timestamptz not null,
  actor_principal_id text references principals(principal_id),
  location_ref text not null default '',
  authority_basis text not null default '',
  evidence_ref text not null default '',
  provenance_ref text not null default '',
  confidence numeric(6,5),
  materiality_class text not null default 'C',
  sensitivity_class text not null default 'internal',
  payload_json text not null,
  admission_state text not null default 'admitted',
  check(materiality_class in ('A','B','C','D','Q'))
);

create index idx_echo_events_enterprise_time on echo_events(enterprise_id, occurred_at);
create index idx_echo_events_subject on echo_events(enterprise_id, subject_type, subject_id);
create index idx_echo_events_type on echo_events(enterprise_id, event_type, occurred_at);

create table vector_definitions (
  vector_code text primary key,
  name text not null,
  purpose text not null,
  recipient_class text not null,
  required_dimensions_json text not null,
  default_strength_class text not null,
  sensitivity_ceiling text not null default 'internal',
  active boolean not null default true,
  check(default_strength_class in ('A','B','C','D','Q'))
);

create table event_vectors (
  event_vector_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  event_id text not null references echo_events(event_id),
  vector_code text not null references vector_definitions(vector_code),
  strength_class text not null,
  weight numeric(8,5) not null default 0,
  passage_state text not null default 'waiting',
  created_at timestamptz not null,
  last_reviewed_at timestamptz,
  expires_at timestamptz,
  reason text not null default '',
  check(strength_class in ('A','B','C','D','Q')),
  check(passage_state in ('waiting','eligible','passed','blocked','quarantined','retired')),
  unique(enterprise_id, event_id, vector_code)
);

create index idx_event_vectors_waiting on event_vectors(enterprise_id, passage_state, strength_class, created_at);

create table chord_definitions (
  chord_code text primary key,
  name text not null,
  purpose text not null,
  consequence_class text not null,
  confirmation_policy text not null,
  active boolean not null default true
);

create table chord_vector_requirements (
  chord_code text not null references chord_definitions(chord_code),
  vector_code text not null references vector_definitions(vector_code),
  minimum_strength_class text not null,
  minimum_weight numeric(8,5) not null default 0,
  required boolean not null default true,
  primary key(chord_code, vector_code),
  check(minimum_strength_class in ('A','B','C','D','Q'))
);

create table chord_candidates (
  candidate_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  chord_code text not null references chord_definitions(chord_code),
  subject_type text not null,
  subject_id text not null,
  status text not null default 'waiting',
  created_at timestamptz not null,
  last_reviewed_at timestamptz,
  confidence numeric(6,5),
  evidence_json text not null default '[]',
  decision_reason text not null default '',
  check(status in ('waiting','eligible','confirmed','rejected','expired','retired'))
);

create index idx_chord_candidates_waiting on chord_candidates(enterprise_id, status, created_at);

create table sweeper_policies (
  policy_id text primary key,
  enterprise_id text references enterprises(enterprise_id),
  target_kind text not null check(target_kind in ('event_vector','chord_candidate')),
  strength_class text not null,
  review_interval_seconds bigint not null check(review_interval_seconds>=60),
  max_wait_seconds bigint,
  action_on_expiry text not null check(action_on_expiry in ('review','escalate','quarantine','retire')),
  active boolean not null default true,
  check(strength_class in ('A','B','C','D','Q'))
);

-- History is preserved. Sweeper retirement removes static from active circulation;
-- it never deletes the originating event or evidence.
