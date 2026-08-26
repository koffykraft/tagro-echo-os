-- TAGRO ECHO OS product tax-completeness layer v0.8
-- Missing HSN/GST is allowed at catalogue admission time. Unknown GST must not be
-- interpreted as a genuine zero rate and must not become billable until populated.

alter table products alter column gst_rate drop not null;

alter table product_commercial_attributes
  add column if not exists gst_known boolean not null default false;

create index if not exists idx_product_commercial_gst_known
  on product_commercial_attributes(enterprise_id, gst_known);
