# Security Policy

## Supported Status

This is a Phase 0 documentation bundle. No production application runtime is included yet.

Security requirements in this document are binding for later phases unless explicitly superseded by a reviewed ADR.

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

