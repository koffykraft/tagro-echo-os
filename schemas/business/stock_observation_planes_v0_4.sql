-- TAGRO ECHO OS stock observation planes v0.4
-- Physical counts are observations. They do not mutate canonical stock movement truth.
-- Missing canonical movement evidence is UNKNOWN, never zero by absence.

create table stock_count_observations (
  observation_id text primary key,
  enterprise_id text not null references enterprises(enterprise_id),
  branch_id text not null references branches(branch_id),
  count_id text references stock_counts(count_id),
  product_id text references products(product_id),
  raw_item_ref text not null default '',
  counted_qty numeric(14,3) not null check(counted_qty>=0),
  canonical_system_qty numeric(14,3),
  variance_to_canonical numeric(14,3),
  observed_at timestamptz not null,
  observed_by text references users(user_id),
  source_type text not null,
  source_ref text not null,
  evidence_id text references evidence_records(evidence_id),
  identity_state text not null default 'resolved'
    check(identity_state in ('resolved','candidate','unresolved')),
  identity_confidence numeric(6,5)
    check(identity_confidence is null or (identity_confidence>=0 and identity_confidence<=1)),
  observation_confidence numeric(6,5)
    check(observation_confidence is null or (observation_confidence>=0 and observation_confidence<=1)),
  provisional_eligible boolean not null default false,
  supersedes_observation_id text references stock_count_observations(observation_id),
  note text not null default '',
  provenance_json text not null default '{}',
  unique(enterprise_id, source_type, source_ref)
);

create index idx_stock_count_observations_subject
  on stock_count_observations(enterprise_id,branch_id,product_id,observed_at);

create index idx_stock_count_observations_unresolved
  on stock_count_observations(enterprise_id,identity_state,observed_at);

-- Provisional operational stock is the latest eligible physical count plus
-- admitted ECHO stock movements that occurred after that count. The count remains
-- the baseline observation; later movements remain separate canonical events.
create view provisional_stock_position as
with ranked_counts as (
  select
    o.*,
    row_number() over (
      partition by o.enterprise_id,o.branch_id,o.product_id
      order by o.observed_at desc,o.observation_id desc
    ) as rn
  from stock_count_observations o
  where o.product_id is not null
    and o.identity_state='resolved'
    and o.provisional_eligible=true
),
latest_counts as (
  select * from ranked_counts where rn=1
)
select
  c.enterprise_id,
  c.branch_id,
  c.product_id,
  c.counted_qty baseline_count_qty,
  coalesce(sum(m.quantity_delta),0) movement_delta_since_count,
  c.counted_qty + coalesce(sum(m.quantity_delta),0) quantity,
  c.observation_id source_observation_id,
  c.observed_at,
  c.source_type,
  c.identity_confidence,
  c.observation_confidence,
  'provisional_count_plus_movements'::text truth_state
from latest_counts c
left join stock_movements m
  on m.enterprise_id=c.enterprise_id
 and m.branch_id=c.branch_id
 and m.product_id=c.product_id
 and m.occurred_at>c.observed_at
group by
  c.enterprise_id,c.branch_id,c.product_id,c.counted_qty,c.observation_id,
  c.observed_at,c.source_type,c.identity_confidence,c.observation_confidence;

-- Canonical and provisional planes remain separate. Consumers must expose both when they differ.
-- The combined provisional projection never creates or edits stock movements.
