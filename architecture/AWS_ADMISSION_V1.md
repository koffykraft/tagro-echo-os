# TAGRO ECHO OS — AWS Admission v1

Status: Architecture admitted for controlled implementation planning. No AWS resource creation is authorised by this document.
Work order: WO-0003
Date: 2026-08-19

## 1. Purpose

Define the first AWS implementation boundary for TAGRO ECHO OS without turning AWS service names into the operating skeleton. Every selected service remains replaceable behind explicit contracts.

## 2. Primary Region

Primary workload Region: `ap-south-1` — Asia Pacific (Mumbai).

Reason:
- the business is initially operating in India;
- Mumbai is an AWS Region in India;
- keeping primary application, database and evidence storage close to the operating geography is the first latency/data-residency assumption to test.

Secondary/DR Region: NOT YET ADMITTED.
Candidate `ap-south-2` (Hyderabad) must be validated per service and against required RTO/RPO before admission.

## 3. Account boundary

Target account pattern:

AWS Organization / governing account
- no ECHO production workload in the management account
- `echo-nonprod` workload account
- `echo-prod` workload account
- security/log-archive account(s) when the organization foundation is admitted

Production and non-production must be separated at account level before production launch. Account structure is based on security/operational boundaries, not district or reporting hierarchy.

## 4. Mobile identity

Admit: Amazon Cognito User Pools as the first identity provider candidate for staff/mobile authentication.

Initial policy:
- no public staff self-registration;
- administrator-created/approved staff identities;
- OIDC/JWT-based application authentication;
- roles/territories remain application authorization data and are checked server-side;
- MFA/passkeys can be admitted after mobile usability testing;
- identity pools are not required unless the client later needs direct temporary AWS credentials.

The mobile application must not receive standing AWS IAM credentials.

## 5. Application ingress and compute

Admit initial pattern:

Mobile/Web PWA
-> Amazon API Gateway HTTP API
-> AWS Lambda application handlers
-> Driver/domain services

Reasons:
- phone clients have one governed application boundary;
- Lambda proxy integration is natively supported by API Gateway HTTP APIs;
- the first 100-counter design does not require persistent application servers merely to exist;
- compute can later be replaced behind API/domain contracts if workload evidence supports containers or another runtime.

The browser/mobile client does not directly mutate the operational database.

## 6. Operational database

Admit semantic/database contract: PostgreSQL-compatible relational operational store.

Required properties:
- ACID transactions for consequential state changes;
- transactional state + outbox/event record where one command changes state;
- unique/idempotency constraints;
- explicit foreign keys/identity relationships where appropriate;
- migration/version discipline;
- point-in-time recovery and tested restore path before production.

Managed AWS deployment mode is DEFERRED between:
- Amazon RDS for PostgreSQL; and
- Amazon Aurora PostgreSQL, including Serverless v2 where supported.

Reason for deferral:
The canonical model does not require Aurora. Exact choice must follow measured connection profile, write/read load, availability requirement and cost benchmark. Aurora Serverless v2 availability varies by engine version and Region, so exact support must be checked at provisioning time.

If Lambda is selected with a relational database, connection-management design must be tested before production; no assumption of unlimited direct database connections is admitted.

## 7. Domain events and asynchronous work

Admit:
- Amazon EventBridge custom event bus for routing admitted domain events between replaceable components;
- Amazon SQS queues for asynchronous consumers;
- SQS FIFO only where ordering/deduplication is materially required, such as narrowly scoped accounting/posting or ordered entity workflows.

Rule:
EventBridge/SQS transport does not itself establish business truth. The authoritative admitted event originates under Driver/domain transaction rules.

Adapter failure must create explicit retry/reconciliation state rather than fabricated success.

## 8. Evidence and raw object storage

Admit Amazon S3 for original evidence and warehouse objects.

Minimum controls before production:
- Block Public Access;
- bucket policies/IAM least privilege;
- server-side encryption;
- Versioning for evidence/raw buckets;
- checksums where ingestion integrity matters;
- lifecycle policy separated from business retention rules.

S3 Object Lock is NOT automatically enabled by this admission. It is a candidate for evidence classes that require WORM-style protection, but retention rules and operational consequences must be approved first because enabling Object Lock is a material governance decision.

## 9. Warehouse and analytical memory

Admit initial warehouse pattern:

S3
- raw
- admitted
- canonical
- curated
- intelligence outputs

Metadata/catalog:
- AWS Glue Data Catalog

Interactive SQL/query:
- Amazon Athena

Transformation:
- deterministic application/Lambda jobs for small flows initially;
- AWS Glue jobs only when scale/ETL complexity justifies them.

Fine-grained data-lake governance:
- AWS Lake Formation is deferred until multi-principal/catalog-level access control requires it.

Preferred analytical file formats should be columnar (for example Parquet) for curated query-heavy data. Open table formats such as Iceberg can be admitted later when update/history semantics justify the added machinery.

## 10. Front-seat / rear-seat deployment boundary

Driver resources:
- authenticated API command handlers;
- operational database writes;
- state transitions;
- event admission/outbox;
- authorised adapters.

Observer resources:
- read admitted event feeds;
- read approved warehouse/operational projections;
- emit findings/attention records only;
- no IAM/database path that permits operational command writes.

The AWS permissions model must enforce this distinction, not merely source-code convention.

## 11. Counter Intelligence

Vision/OCR/AI providers are NOT yet admitted as a single fixed AWS service.

Counter Intelligence contract will accept:
- photo/image evidence;
- barcode/QR observations;
- OCR/text extraction;
- voice/text input;
- model/serial candidates;
- quantity/part candidates;
- confidence and provenance.

AI/model services can be replaced without changing admitted business-event contracts.

## 12. Offline/mobile tolerance

The counter client may capture draft/offline observations and commands with locally generated command IDs/idempotency keys.

Offline capture is not equivalent to committed cloud truth.
On reconnect:
- authenticate;
- submit through normal Driver authority;
- deduplicate/idempotently process;
- return accepted/rejected/review-required result;
- preserve capture time separately from cloud admission time.

## 13. Not admitted yet

- production AWS account IDs;
- VPC/CIDR layout;
- exact PostgreSQL managed service/machine size;
- production database credentials/secrets;
- DR Region;
- Bedrock/SageMaker/Rekognition/Textract or any single AI provider as mandatory;
- production WhatsApp/email provider;
- BUSY cloud-to-local writer implementation;
- bank APIs;
- QuickSight or another BI presentation layer;
- production deployment.

## 14. Evidence basis

This admission was checked against current AWS primary documentation on:
- AWS multi-account and workload separation;
- Asia Pacific (Mumbai) Region identification;
- Cognito user pools/OIDC/JWT authentication;
- API Gateway HTTP API Lambda proxy integrations;
- Aurora Serverless v2 region/version constraints;
- EventBridge targets and SQS/FIFO behavior;
- S3 Versioning/Object Lock/data integrity;
- Athena and AWS Glue Data Catalog integration.

No certification, SLA, availability, cost or production-readiness claim is made by this document.
