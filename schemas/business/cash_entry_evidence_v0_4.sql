-- TAGRO ECHO OS Closing Cash entry evidence v0.4
-- Additive shared-runtime dock. Entries remain evidence; P&L classification is explicit only.

create table cash_day_sessions (
  session_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  business_date date not null,
  opening_cash numeric(14,2) not null check(opening_cash>=0),
  declared_closing numeric(14,2) check(declared_closing>=0),
  status text not null check(status in ('draft','submitted','approved','superseded')),
  created_at timestamptz not null,
  created_by text not null references users(user_id),
  submitted_at timestamptz,
  submitted_by text references users(user_id),
  approved_at timestamptz,
  approved_by text references users(user_id),
  supersedes_session_id text references cash_day_sessions(session_id),
  note text not null default ''
);

create unique index cash_day_sessions_one_active_day
  on cash_day_sessions(enterprise_id,branch_id,business_date)
  where status in ('draft','submitted','approved');

create table cash_entry_evidence (
  entry_id text primary key,
  session_id text not null references cash_day_sessions(session_id),
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  business_date date not null,
  entry_type text not null check(entry_type in (
    'cash_sale','cash_receipt','service_cash_receipt','other_cash_in',
    'upi_receipt','card_receipt','bank_receipt','service_noncash_receipt',
    'expense_cash','expense_noncash','allocation_cash','deposit_cash',
    'transfer_cash_out','bank_transfer_out'
  )),
  channel text not null check(channel in ('cash','upi','card','bank','other')),
  amount numeric(14,2) not null check(amount>0),
  reference text not null default '',
  evidence_ref text not null default '',
  note text not null default '',
  occurred_at timestamptz not null,
  actor_id text not null references users(user_id),
  idempotency_key text not null,
  classification_category text,
  classification_role text not null default 'unknown' check(classification_role in (
    'direct_selling_cost','branch_operating_expense','central_overhead','finance_cost',
    'non_operating','capital_movement','internal_transfer','unknown'
  )),
  classification_confidence text not null default 'unknown' check(classification_confidence in ('exact','strong','weak','unknown')),
  unique(enterprise_id,idempotency_key)
);

create index cash_entry_evidence_session_idx on cash_entry_evidence(session_id,occurred_at,entry_id);
create index cash_entry_evidence_period_idx on cash_entry_evidence(enterprise_id,business_date,branch_id);

create view cash_day_session_review as
select
  s.session_id,s.enterprise_id,s.branch_id,s.business_date,s.opening_cash,s.declared_closing,s.status,
  coalesce(sum(case when e.entry_type in ('cash_sale','cash_receipt','service_cash_receipt','other_cash_in') then e.amount else 0 end),0)::numeric(14,2) as cash_in,
  coalesce(sum(case when e.entry_type in ('expense_cash','deposit_cash','transfer_cash_out','allocation_cash') then e.amount else 0 end),0)::numeric(14,2) as cash_out,
  coalesce(sum(case when e.entry_type in ('upi_receipt','card_receipt','bank_receipt','service_noncash_receipt') then e.amount else 0 end),0)::numeric(14,2) as noncash_in,
  coalesce(sum(case when e.entry_type in ('expense_noncash','bank_transfer_out') then e.amount else 0 end),0)::numeric(14,2) as noncash_out,
  (s.opening_cash
   +coalesce(sum(case when e.entry_type in ('cash_sale','cash_receipt','service_cash_receipt','other_cash_in') then e.amount else 0 end),0)
   -coalesce(sum(case when e.entry_type in ('expense_cash','deposit_cash','transfer_cash_out','allocation_cash') then e.amount else 0 end),0))::numeric(14,2) as expected_closing,
  case when s.declared_closing is null then null else
    (s.declared_closing-(s.opening_cash
      +coalesce(sum(case when e.entry_type in ('cash_sale','cash_receipt','service_cash_receipt','other_cash_in') then e.amount else 0 end),0)
      -coalesce(sum(case when e.entry_type in ('expense_cash','deposit_cash','transfer_cash_out','allocation_cash') then e.amount else 0 end),0)))::numeric(14,2)
  end as variance,
  count(e.entry_id)::integer as entry_count
from cash_day_sessions s
left join cash_entry_evidence e on e.session_id=s.session_id
 group by s.session_id,s.enterprise_id,s.branch_id,s.business_date,s.opening_cash,s.declared_closing,s.status;
