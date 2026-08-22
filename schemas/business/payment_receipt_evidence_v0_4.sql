-- TAGRO ECHO OS payment receipt evidence v0.4
-- A sale does not prove receipt. Payment is separate operational evidence.
-- Staff affirmation is not bank/cash reconciliation and must remain explicitly unreconciled.

create table payment_receipts (
  payment_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  received_at timestamptz not null,
  amount numeric(14,2) not null check(amount>0),
  method text not null check(method in ('cash','upi','card','bank','other')),
  evidence_state text not null
    check(evidence_state in ('staff_affirmed_unreconciled','reconciled','voided')),
  actor_id text not null references users(user_id),
  source_type text not null default 'billing',
  source_ref text not null,
  idempotency_key text not null,
  reference text not null default '',
  provenance_json text not null default '{}',
  unique(enterprise_id,idempotency_key)
);

create table payment_allocations (
  payment_id text not null references payment_receipts(payment_id),
  sale_id text not null references sale_headers(sale_id),
  amount numeric(14,2) not null check(amount>0),
  allocation_state text not null
    check(allocation_state in ('staff_affirmed_unreconciled','reconciled','voided')),
  primary key(payment_id,sale_id)
);

create index idx_payment_receipts_branch_time
  on payment_receipts(enterprise_id,branch_id,received_at);

create index idx_payment_allocations_sale
  on payment_allocations(sale_id);

-- No direct bank-transaction foreign key is created here.
-- Bank/cash corroboration remains a separate candidate chord and reconciliation event.
