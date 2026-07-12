# Threat Model Summary

## Assets

- Subscriber records
- Sensitive identity fields
- Payment records, allocations, unmatched-payment cases, and future M-PESA webhook and reconciliation records
- Wallet balances and ledger entries
- Invoices and receipts
- Router credentials
- Per-NAS RADIUS shared secret references
- Staff sessions
- Audit logs
- Backups
- Uploaded statements

## Trust Boundaries

- Public internet to Caddy or development reverse proxy
- Public webhook endpoint to Django request handling
- Staff browser to authenticated Django session
- Django app to PostgreSQL
- Django app to task broker
- Celery workers to broker, database, RouterOS, and FreeRADIUS
- Backup process to off-site storage
- Uploaded CSV files to reconciliation parser
- Secure settings UI to secret provider
- Lab network integrations to production network integrations

## Key Threats And Controls

| Threat | Control |
| --- | --- |
| Duplicate provider callbacks or retries double-credit subscriber | Provider transaction uniqueness, transactional locks, allocation idempotency tests |
| Future webhook replay using altered identifiers | Persist raw webhook events, validate against provider profile, use canonical payment uniqueness, reject inconsistent replay payloads, audit replay attempts |
| Future forged or malformed callbacks | Strict validation, sandbox-proven callback contract, configured callback URLs, payload persistence, rejection path |
| Assuming callback signatures or fixed Safaricom source IPs without evidence | Block M-PESA implementation until sandbox evidence is collected; do not rely on source-IP allowlisting alone |
| Concurrent renewal and allocation races | Database transactions, row-level locks, allocation idempotency keys, deterministic renewal services |
| Lost payment during RouterOS or RADIUS outage | Persist webhook, payment, allocation, and ledger state first; retry network jobs separately |
| Staff member performs unauthorized financial adjustment | RBAC, approval workflow, reason capture, audit events |
| Support staff sees sensitive identity data | Field-level masking and permission checks |
| Router credentials or RADIUS secrets leak in logs | Secret redaction, encrypted settings or secret references, log tests |
| Secret exposure through Django admin | Avoid registering secret plaintext fields, mask credential references, restrict admin views, test redaction |
| CSV formula injection in exports | Escape dangerous leading characters |
| CSV files with oversized rows or excessive record counts | File size limits, row count limits, streaming parser limits, rejection with audit event |
| Malicious statement upload | File size/type checks, parser isolation, validation errors |
| Malicious subscriber notes or stored XSS | Server-side escaping, safe template defaults, sanitization for rich text if ever enabled |
| Ledger tampering | Append-only entries, restricted admin, audit events, database constraints |
| Reversal deletes history | Compensating entries only |
| Mass subscriber disconnection due to software error | Dry-run default, batch limits, approval gates, circuit breakers, staged rollout, audit and rollback plan |
| Router write damages production network | Dry-run default, allowlist, lab validation, Owner approval |
| A lab router accidentally marked production | Environment field, production-readiness checks, visual environment banner, confirmation gates |
| SSRF through configurable router or callback URLs | URL allowlists, private network validation rules, no arbitrary outbound fetches from user-entered URLs |
| Compromised Celery worker | Least-privilege credentials, separate worker service account, network egress limits, audit unusual job behavior |
| Compromised broker | Treat broker as untrusted transport, keep financial source of truth in PostgreSQL, signed or validated task payloads where practical |
| Backup cannot restore | Scheduled restore tests and documented recovery |
| Stolen backup archives | Backup encryption, off-site storage review, key recovery procedure, access logging |
| Audit-log deletion by privileged users | Application-level append-only model, no ordinary update/delete UI, restricted admin, database backups; do not claim cryptographic immutability |
| Clock drift and incorrect expiry calculations | UTC persisted timestamps, Africa/Nairobi business calculations, NTP monitoring, timezone tests |
| Callback denial-of-service | Rate limits, request size limits, fast persistence, worker queue backpressure, alerting |
| Dependency vulnerability | Lockfile, dependency scanning, security updates |
| Session hijacking | Secure cookies, CSRF, session timeout, TOTP for privileged roles |

## Required Security Tests

Phase 1 and later test suites must include:

- Secrets do not appear in logs.
- Unauthorized staff actions are rejected.
- Financial records cannot be hard-deleted.
- CSV exports prevent formula injection.
- Router writes are impossible in dry-run mode.
- Duplicate provider transaction processing credits once.
- Concurrent duplicate provider callbacks or retries credit once.
- Audit events cannot be updated or deleted through application code.
- Environment banners and production-readiness checks prevent lab-to-production confusion.
