-- TAGRO ECHO OS purchase entry v0.10
-- Recording a supplier invoice / goods receipt for stock bought into a branch, with
-- a GST breakdown (CGST+SGST for intra-Kerala suppliers, IGST for out-of-state
-- suppliers -- same convention already used by the TAGRO OS mobile purchase-entry
-- feature, so the two systems agree on how a supplier invoice is taxed).
--
-- Deliberately separate from purchase_orders/purchase_order_lines (an order TAGRO
-- raises against a supplier from the catalog, with a catalog-linked product_id
-- required on every line): a purchase entry records whatever a supplier's invoice
-- actually says -- item names, rates and GST% exactly as billed, which may not
-- match any catalog part at all (a workshop consumable, a one-off local purchase,
-- etc). product_id is therefore optional at the line level; when it is present the
-- line is understood to be the named catalog product (HSN/TAGRO-name lookups can
-- follow the product), and when it is absent the line stands entirely on its own
-- typed name, rate and GST%.

-- GST cannot be inferred from a fixed head-office state: each operating branch
-- is the recipient of the supply.  Unknown state is intentionally nullable so
-- the runtime can stop for review instead of silently applying the wrong tax.
alter table branches add column if not exists gst_state_code text;
alter table branches drop constraint if exists branches_gst_state_code_check;
alter table branches add constraint branches_gst_state_code_check
  check (gst_state_code is null or gst_state_code ~ '^[0-9]{2}$');

create table purchase_entries (
  entry_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  supplier_id text not null references suppliers(supplier_id),
  entry_number text not null,
  status text not null default 'draft' check(status in ('draft','recorded')),
  supplier_gstin text not null default '',
  place_of_supply text not null default '',
  invoice_number text not null default '',
  invoice_date date,
  shipment_reference text not null default '',
  transporter text not null default '',
  shipment_note text not null default '',
  purchase_note text not null default '',
  taxable_total numeric(14,2) not null default 0,
  cgst_total numeric(14,2) not null default 0,
  sgst_total numeric(14,2) not null default 0,
  igst_total numeric(14,2) not null default 0,
  grand_total numeric(14,2) not null default 0,
  created_by text not null references users(user_id),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique(enterprise_id, entry_number)
);

create index idx_purchase_entries_branch_status
  on purchase_entries(enterprise_id, branch_id, status, created_at);

create table purchase_entry_lines (
  entry_id text not null references purchase_entries(entry_id),
  line_no integer not null,
  product_id text references products(product_id),
  item_name text not null,
  hsn_code text not null default '',
  unit text not null default 'nos',
  quantity numeric(14,3) not null check(quantity>0),
  unit_rate numeric(14,2) not null check(unit_rate>=0),
  gst_rate numeric(6,3) not null default 0,
  taxable_amount numeric(14,2) not null,
  cgst_amount numeric(14,2) not null default 0,
  sgst_amount numeric(14,2) not null default 0,
  igst_amount numeric(14,2) not null default 0,
  line_total numeric(14,2) not null,
  primary key(entry_id,line_no)
);

-- A per-enterprise running counter behind the human-facing "PE-000123" entry
-- number. Allocated once, at create time only; editing a draft keeps its number.
create table purchase_entry_sequences (
  enterprise_id text primary key references enterprises(enterprise_id),
  next_seq integer not null default 1
);
