-- TAGRO ECHO OS platform identity constraints v0.2.1
-- Additive hardening after the initial SaaS-safe v0.2 foundation.

create unique index ux_principals_external_identity_ref
on principals(external_identity_ref)
where external_identity_ref <> '';

create index idx_enterprise_memberships_principal
on enterprise_memberships(principal_id, status, enterprise_id);

create index idx_enterprise_entitlements_active
on enterprise_entitlements(enterprise_id, status, capability_code);
