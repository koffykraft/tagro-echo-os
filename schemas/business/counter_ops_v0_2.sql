-- TAGRO ECHO OS counter operations schema v0.2
-- Enterprise-scoped operational state; events/evidence remain separately governed.

create table purchase_orders (
  po_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  supplier_id text not null references suppliers(supplier_id),
  created_at timestamptz not null,
  status text not null,
  created_by text not null references users(user_id),
  approved_by text references users(user_id),
  approved_at timestamptz
);

create table purchase_order_lines (
  po_id text not null references purchase_orders(po_id),
  line_no integer not null,
  product_id text not null references products(product_id),
  quantity numeric(14,3) not null check(quantity>0),
  unit_price numeric(14,2),
  note text not null default '',
  primary key(po_id,line_no)
);

create table stock_transfers (
  transfer_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  from_branch_id text not null references branches(branch_id),
  to_branch_id text not null references branches(branch_id),
  requested_at timestamptz not null,
  status text not null,
  requested_by text not null references users(user_id),
  dispatched_by text references users(user_id),
  dispatched_at timestamptz,
  received_by text references users(user_id),
  received_at timestamptz,
  check(from_branch_id<>to_branch_id)
);

create table stock_transfer_lines (
  transfer_id text not null references stock_transfers(transfer_id),
  line_no integer not null,
  product_id text not null references products(product_id),
  quantity numeric(14,3) not null check(quantity>0),
  primary key(transfer_id,line_no)
);

create table stock_counts (
  count_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  created_by text not null references users(user_id),
  created_at timestamptz not null,
  status text not null,
  finalized_by text references users(user_id),
  finalized_at timestamptz
);

create table stock_count_lines (
  count_id text not null references stock_counts(count_id),
  product_id text not null references products(product_id),
  system_qty numeric(14,3) not null,
  counted_qty numeric(14,3) not null,
  variance numeric(14,3) not null,
  evidence_ids text not null default '',
  primary key(count_id,product_id)
);

create table evidence_records (
  evidence_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text references branches(branch_id),
  source_type text not null,
  content_hash text not null,
  mime_type text not null,
  captured_at timestamptz not null,
  actor_principal_id text references principals(principal_id),
  source_ref text not null default '',
  note text not null default ''
);

create table inference_proposals (
  proposal_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  evidence_id text not null references evidence_records(evidence_id),
  proposal_type text not null,
  payload_json text not null,
  confidence numeric(6,5),
  created_at timestamptz not null,
  provider_ref text not null default '',
  status text not null default 'proposed'
);

create table accepted_observations (
  observation_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  proposal_id text not null unique references inference_proposals(proposal_id),
  evidence_id text not null references evidence_records(evidence_id),
  payload_json text not null,
  accepted_at timestamptz not null,
  accepted_by text not null references users(user_id)
);

create table sync_envelopes (
  idempotency_key text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  device_id text not null,
  counter_id text not null references branches(branch_id),
  sequence bigint not null check(sequence>=0),
  payload_type text not null,
  payload_json text not null,
  created_at timestamptz not null,
  payload_hash text not null,
  acknowledged_at timestamptz,
  unique(enterprise_id, device_id, sequence)
);
