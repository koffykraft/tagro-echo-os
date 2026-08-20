-- TAGRO ECHO OS operational extensions v0.3
-- Service, cash and bank evidence with explicit Enterprise ownership.

create table machines (
  machine_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  customer_id text not null references customers(customer_id),
  product_id text references products(product_id),
  model text not null,
  serial_no text not null default '',
  purchase_date date,
  source text not null
);

create table service_jobs (
  job_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  customer_id text not null references customers(customer_id),
  machine_id text not null references machines(machine_id),
  opened_at timestamptz not null,
  complaint text not null,
  status text not null,
  observations text not null default '',
  estimate_id text
);

create table service_events (
  event_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  job_id text not null references service_jobs(job_id),
  occurred_at timestamptz not null,
  event_type text not null,
  note text not null default '',
  actor_id text not null references users(user_id)
);

create table cash_closings (
  closing_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  business_date date not null,
  opening_cash numeric(14,2) not null check(opening_cash>=0),
  cash_sales numeric(14,2) not null check(cash_sales>=0),
  other_cash_in numeric(14,2) not null check(other_cash_in>=0),
  cash_expenses numeric(14,2) not null check(cash_expenses>=0),
  cash_deposits_or_transfers numeric(14,2) not null check(cash_deposits_or_transfers>=0),
  declared_closing numeric(14,2) not null check(declared_closing>=0),
  recorded_at timestamptz not null,
  actor_id text not null references users(user_id),
  note text not null default '',
  unique(enterprise_id,branch_id,business_date)
);

create view cash_closing_review as
select *,
  opening_cash+cash_sales+other_cash_in-cash_expenses-cash_deposits_or_transfers as expected_closing,
  declared_closing-(opening_cash+cash_sales+other_cash_in-cash_expenses-cash_deposits_or_transfers) as variance
from cash_closings;

create table bank_transactions (
  transaction_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  statement_id text not null,
  source_file text not null,
  source_row integer not null check(source_row>0),
  account_id text not null,
  transaction_date date not null,
  value_date date,
  direction text not null check(direction in ('credit','debit')),
  amount numeric(14,2) not null check(amount>0),
  narration text not null,
  reference text not null default '',
  balance numeric(14,2),
  unique(enterprise_id, statement_id, source_row)
);

-- No direct bank->sale/payment foreign key: correlation is a candidate relationship/chord
-- until the owning contract validates and confirms it.
