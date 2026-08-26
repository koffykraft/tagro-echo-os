-- TAGRO ECHO OS spectral routing / VIBGYOR prism foundation v0.2.2
-- The event remains whole truth. Spectral decomposition governs relevance and routing;
-- a non-matching spectral projection is semantically inert for that receiver.

create table spectral_bands (
  spectrum_code text primary key,
  name text not null,
  ordinal integer not null unique,
  semantic_scope text not null default 'contract_defined',
  active boolean not null default true,
  check(spectrum_code in ('V','I','B','G','Y','O','R')),
  check(ordinal between 1 and 7)
);

insert into spectral_bands (spectrum_code, name, ordinal)
values
  ('V','Violet',1),
  ('I','Indigo',2),
  ('B','Blue',3),
  ('G','Green',4),
  ('Y','Yellow',5),
  ('O','Orange',6),
  ('R','Red',7);

alter table vector_definitions
  add column spectrum_code text references spectral_bands(spectrum_code);

create table spectral_receiver_rules (
  rule_id text primary key,
  enterprise_id text references enterprises(enterprise_id),
  recipient_class text not null,
  spectrum_code text not null references spectral_bands(spectrum_code),
  vector_code text references vector_definitions(vector_code),
  active boolean not null default true,
  admitted_reason text not null,
  unique(enterprise_id, recipient_class, spectrum_code, vector_code)
);

-- Presence at a receiver does not create business meaning.
-- Only a matching admitted spectral rule may make a projection eligible for a Chord or consequence.
