-- Lossless BUSY read/write boundary.  Normalized fields support TAGRO pages;
-- raw/unknown fields preserve the complete BUSY record for round trips.
create table if not exists busy_round_trip_records (
  record_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text references branches(branch_id),
  record_kind text not null check(record_kind in
    ('sale','purchase','receipt','payment','item_master','account_master')),
  operation text not null check(operation in ('import','create','update')),
  business_record_id text not null default '',
  business_date date,
  busy_company_code text not null default '',
  busy_financial_year text not null default '',
  busy_table text not null default '',
  busy_voucher_type text not null default '',
  busy_voucher_series text not null default '',
  busy_voucher_number text not null default '',
  busy_voucher_code text not null default '',
  busy_master_code text not null default '',
  normalized_json jsonb not null,
  busy_raw_json jsonb not null default '{}'::jsonb,
  busy_unknown_json jsonb not null default '{}'::jsonb,
  mapping_version text not null,
  mapping_status text not null check(mapping_status in
    ('unmapped','partial','validated')),
  write_status text not null check(write_status in
    ('read_only','blocked','ready','written','rejected')),
  uncertainty text not null default '',
  source_system text not null,
  source_file text not null default '',
  source_record text not null default '',
  source_hash text not null default '',
  idempotency_key text not null,
  created_by text not null default '',
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique(enterprise_id,idempotency_key)
);

create index if not exists idx_busy_round_trip_lookup
  on busy_round_trip_records(enterprise_id,branch_id,record_kind,business_date);
create index if not exists idx_busy_round_trip_write_queue
  on busy_round_trip_records(enterprise_id,write_status,mapping_status,updated_at);

create table if not exists busy_round_trip_reviews (
  review_id text primary key,
  record_id text not null references busy_round_trip_records(record_id),
  field_path text not null,
  issue_code text not null,
  source_value_json jsonb,
  proposed_value_json jsonb,
  status text not null default 'open' check(status in ('open','resolved','rejected')),
  resolution_note text not null default '',
  reviewed_by text not null default '',
  created_at timestamptz not null,
  resolved_at timestamptz
);

