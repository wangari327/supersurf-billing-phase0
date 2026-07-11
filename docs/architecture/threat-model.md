# Threat Model Summary

## Assets

- Subscriber records
- Sensitive identity fields
- M-PESA callbacks and payment records
- Wallet balances and ledger entries
- Invoices and receipts
- Router credentials
- RADIUS shared secrets
- Staff sessions
- Audit logs
- Backups
- Uploaded statements

## Trust Boundaries

- Public internet to Caddy
- Caddy to Django app
- Daraja callback endpoint to payment processing
- Staff browser to authenticated Django session
- Django app to PostgreSQL
- Django app to task broker
- Celery workers to RouterOS and FreeRADIUS
- Backup process to off-site storage
- Uploaded CSV files to reconciliation parser

## Key Threats And Controls

| Threat | Control |
| --- | --- |
| Duplicate M-PESA callbacks double-credit subscriber | Provider transaction uniqueness, transactional locks, idempotency tests |
| Forged or malformed callbacks | Strict validation, configured callback URLs, payload persistence, rejection path |
| Lost payment during RouterOS or RADIUS outage | Persist payment and ledger first; retry network jobs separately |
| Staff member performs unauthorized financial adjustment | RBAC, approval workflow, audit events |
| Support staff sees sensitive identity data | Field-level masking and permission checks |
| Router credentials leak in logs | Secret redaction, encrypted settings, log tests |
| CSV formula injection in exports | Escape dangerous leading characters |
| Malicious statement upload | File size/type checks, parser isolation, validation errors |
| Ledger tampering | Append-only entries, restricted admin, audit events, database constraints |
| Reversal deletes history | Compensating entries only |
| Router write damages production network | Dry-run default, allowlist, lab validation, Owner approval |
| Backup cannot restore | Scheduled restore tests and documented recovery |
| Dependency vulnerability | Lockfile, dependency scanning, security updates |
| Session hijacking | Secure cookies, CSRF, session timeout, TOTP for privileged roles |

## Required Security Tests

Phase 1 and later test suites must include:

- Secrets do not appear in logs.
- Unauthorized staff actions are rejected.
- Financial records cannot be hard-deleted.
- CSV exports prevent formula injection.
- Router writes are impossible in dry-run mode.
- Duplicate callback processing credits once.
- Concurrent duplicate callbacks credit once.

