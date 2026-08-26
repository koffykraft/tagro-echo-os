-- ECHO product unit conversion foundation v0.9
-- Preserve BUSY's existing stock/sale unit; conversions are explicit evidence only.

create table if not exists product_unit_conversions (
  conversion_id text primary key,
  enterprise_id text not null,
  product_id text not null,
  from_unit text not null,
  to_unit text not null,
  multiplier numeric(18,6) not null,
  usage_type text not null default 'general',
  branch_id text null,
  source_ref text not null default '',
  provenance_json text not null default '{}',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint product_unit_conversion_positive check (multiplier > 0),
  constraint product_unit_conversion_distinct check (lower(from_unit) <> lower(to_unit)),
  constraint product_unit_conversion_product_fk foreign key (product_id) references products(product_id),
  constraint product_unit_conversion_enterprise_fk foreign key (enterprise_id) references enterprises(enterprise_id),
  constraint product_unit_conversion_branch_fk foreign key (branch_id) references branches(branch_id),
  constraint product_unit_conversion_identity unique (enterprise_id,product_id,from_unit,to_unit,usage_type,branch_id)
);

create index if not exists idx_product_unit_conversions_lookup
  on product_unit_conversions(enterprise_id,product_id,active);

comment on table product_unit_conversions is
  'Explicit quantity conversions. BUSY unit remains canonical operational unit; no conversion is inferred from names such as reel/links.';
