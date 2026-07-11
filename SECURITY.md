# Security Policy

## Supported Status

This repository includes the Phase 1 foundation runtime. It is not production-ready for payments, billing, subscriber management, RADIUS, or RouterOS operations.

Security requirements in this document are binding for later phases unless explicitly superseded by a reviewed ADR.

## Implemented In Phase 1

- Custom Django staff user model
- Django Groups and Permissions for the approved roles
- Login, logout, password change, and session expiry
- django-axes login throttling
- django-otp installed for optional TOTP foundation
- Append-only application-level `AuditEvent`
- Audit redaction helper
- Secret redaction logging filter
- Health and readiness endpoints
- Environment banner
- Production deployment checks
- Local secret scanning script
- GitHub Actions for tests, checks, secret scanning, vulnerability scanning, and licence report

## Audit Immutability Boundary

Phase 1.1 rejects application-level `AuditEvent` instance updates, deletes, queryset `update()`, queryset `delete()`, and `bulk_update()`. The Django admin is read-only for audit events.

This is not database-level immutability. Database administrators, direct SQL access, compromised database credentials, or filesystem-level database access can still alter records. Stronger database-level immutability, retention controls, and backup verification should be reviewed before financial workflows begin.

## Sensitive Data

Sensitive values include:

- M-PESA consumer keys and consumer secrets
- Daraja OAuth tokens
- Callback validation secrets
- RouterOS usernames, passwords, certificates, and private keys
- RADIUS shared secrets
- WireGuard private keys
- Django secret keys
- Encryption keys
- Session cookies
- Full national ID numbers
- Passport numbers
- KRA PINs
- Company registration numbers where sensitive
- Bulk subscriber exports

Sensitive values must not appear in logs, URLs, screenshots, support notes, ordinary exports, or audit summaries.

## Required Controls For Later Phases

- Django password hashing with current supported algorithms
- CSRF protection
- Secure cookie configuration
- Session timeout and rotation on privilege change
- Login throttling and account-lockout controls
- Optional mandatory TOTP for privileged roles
- Least-privilege RBAC
- Encrypted integration credentials
- Secret rotation procedure
- Append-only audit logging with redaction
- Strict webhook validation
- Idempotent payment processing
- CSV formula-injection prevention
- Safe file upload validation
- Dependency scanning
- Static analysis
- Backup encryption and restore tests
- Production security headers

## Payment Security

M-PESA callbacks must be persisted before business processing. Duplicate callbacks must not double-credit. Invalid callbacks must credit nothing. Reversals must create compensating ledger entries rather than deleting history.

Till payments must not be matched by amount alone.

M-PESA implementation has not begun. It is blocked until sandbox evidence is collected in `docs/research/mpesa-sandbox-evidence-checklist.md`.

## Network Safety

Router writes must default to dry-run. Any real RouterOS action must be:

- Explicitly enabled in secure settings
- Role-restricted
- Logged in the audit trail
- Idempotent where possible
- Limited to allowlisted commands
- Blocked from changing WAN, routing, CAKE, WireGuard, watchdog, backup, or unrelated router settings

## Reporting A Vulnerability

During early development, report suspected vulnerabilities to the SuperSurf owner through the private project channel. Do not include secrets or full identity numbers in reports.
