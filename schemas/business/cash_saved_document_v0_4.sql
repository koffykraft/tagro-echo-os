-- TAGRO ECHO OS Closing Cash saved document v0.4
-- Stores the exact confirmed user document separately from derived cash evidence.

create table cash_saved_documents (
  document_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  session_id text not null references cash_day_sessions(session_id),
  branch_id text not null references branches(branch_id),
  business_date date not null,
  saved_at timestamptz not null,
  saved_by text not null references users(user_id),
  entered_for_label text not null default '',
  context_switch_reason text not null default '',
  document_schema text not null,
  document_json jsonb not null,
  rendered_image_png bytea,
  rendered_image_sha256 text,
  rendered_image_mime text,
  source_idempotency_key text not null,
  unique(enterprise_id, source_idempotency_key)
);

create index cash_saved_documents_day_idx
  on cash_saved_documents(enterprise_id,branch_id,business_date,saved_at);
