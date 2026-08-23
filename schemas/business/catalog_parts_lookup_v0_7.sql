-- TAGRO ECHO OS canonical catalogue / parts lookup layer v0.7
-- This is an operational reference plane above canonical products/prices.
-- It is manufacturer-neutral: STIHL, ECHO, Jain and future suppliers use the same structure.

create table if not exists catalog_manufacturers (
  manufacturer_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  code text not null,
  name text not null,
  active boolean not null default true,
  source_ref text not null default '',
  unique(enterprise_id, code)
);

create table if not exists catalog_models (
  model_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  manufacturer_id text not null references catalog_manufacturers(manufacturer_id),
  model_code text not null,
  model_name text not null,
  product_id text references products(product_id),
  category text not null default '',
  active boolean not null default true,
  source_ref text not null default '',
  provenance_json text not null default '{}',
  unique(enterprise_id, manufacturer_id, model_code)
);

create index if not exists idx_catalog_models_lookup
  on catalog_models(enterprise_id, model_code, model_name);

create table if not exists product_aliases (
  alias_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  product_id text not null references products(product_id),
  alias_type text not null,
  alias_value text not null,
  branch_code text not null default '',
  source_ref text not null default '',
  active boolean not null default true,
  unique(enterprise_id, alias_type, alias_value, branch_code)
);

create index if not exists idx_product_alias_lookup
  on product_aliases(enterprise_id, lower(alias_value));

create table if not exists product_supersessions (
  supersession_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  old_product_id text not null references products(product_id),
  new_product_id text not null references products(product_id),
  effective_from date,
  note text not null default '',
  source_ref text not null default '',
  unique(enterprise_id, old_product_id, new_product_id)
);

create table if not exists catalog_documents (
  document_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  manufacturer_id text references catalog_manufacturers(manufacturer_id),
  document_type text not null,
  title text not null,
  document_ref text not null,
  revision text not null default '',
  effective_from date,
  source_ref text not null default '',
  content_hash text not null default '',
  active boolean not null default true,
  unique(enterprise_id, document_ref, revision)
);

create table if not exists catalog_diagrams (
  diagram_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  model_id text not null references catalog_models(model_id),
  document_id text references catalog_documents(document_id),
  diagram_code text not null,
  title text not null,
  page_ref text not null default '',
  image_ref text not null default '',
  sort_order integer not null default 0,
  active boolean not null default true,
  unique(enterprise_id, model_id, diagram_code)
);

create index if not exists idx_catalog_diagrams_model
  on catalog_diagrams(enterprise_id, model_id, sort_order);

create table if not exists catalog_callouts (
  callout_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  diagram_id text not null references catalog_diagrams(diagram_id),
  callout_no text not null,
  product_id text references products(product_id),
  manufacturer_part_no text not null default '',
  description text not null default '',
  quantity numeric(14,3),
  note text not null default '',
  source_ref text not null default '',
  unique(enterprise_id, diagram_id, callout_no, manufacturer_part_no)
);

create index if not exists idx_catalog_callout_part
  on catalog_callouts(enterprise_id, manufacturer_part_no);
create index if not exists idx_catalog_callout_product
  on catalog_callouts(enterprise_id, product_id);

create table if not exists product_compatibility (
  compatibility_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  product_id text not null references products(product_id),
  model_id text not null references catalog_models(model_id),
  compatibility_type text not null default 'fits',
  note text not null default '',
  source_ref text not null default '',
  unique(enterprise_id, product_id, model_id, compatibility_type)
);

create index if not exists idx_product_compatibility_model
  on product_compatibility(enterprise_id, model_id, product_id);
