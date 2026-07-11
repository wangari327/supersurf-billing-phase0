# Phase 0 Report

## 1. Summary Of Proposed SuperSurf Architecture

SuperSurf Billing should be a Django modular monolith using PostgreSQL as the source of truth, Celery for asynchronous work, a reviewed broker/cache, Django templates with HTMX and Tailwind for the operator UI, FreeRADIUS for PPPoE authentication/accounting, MikroTik RouterOS integration behind a dry-run adapter, and Caddy for TLS reverse proxying.

Financial truth is persisted before network action. Payments, wallet allocation, ledger entries, and audit events live in PostgreSQL. RouterOS and RADIUS actions are queued, audited, retryable, and dry-run by default.

## 2. Repository Files Created

See the root of this Phase 0 bundle and the `docs/` tree. Key files:

- `AGENTS.md`
- `README.md`
- `SECURITY.md`
- `DEPENDENCIES.md`
- `THIRD_PARTY_NOTICES.md`
- `.env.example`
- `docs/product/supersurf-brand.md`
- `docs/kenya/*.md`
- `docs/research/*.md`
- `docs/reuse/*.md`
- `docs/architecture/*.md`
- `docs/adr/*.md`
- `docs/implementation/*.md`

## 3. SuperSurf And Kenya Product Decisions

- SuperSurf is the default brand.
- Default product label is SuperSurf Billing.
- Kenya defaults are mandatory: KE, KES, KSh, Africa/Nairobi, en-KE, DD/MM/YYYY, 24-hour time, Monday week start, +254.
- Money is integer minor units internally.
- Tax settings are configurable and disabled until explicitly configured.
- eTIMS is deferred with only an extension point.
- Kenyan address fields prioritize county, locality, estate, landmark, GPS, installation directions, service notes, and access-point notes.
- Sensitive identity fields are optional, masked, access-controlled, excluded from ordinary exports, and absent from logs.

## 4. Open-Source Projects And Packages Investigated

Investigated Django, DRF, Celery, django-celery-beat, django-htmx, django-filter, django-guardian, rules, django-otp, django-two-factor-auth, django-simple-history, django-auditlog, django-axes, phonenumbers, django-phonenumber-field, Babel, django-money, django-ledger, django-hordak, python-accounting, httpx, tenacity, structlog, django-structlog, django-health-check, django-import-export, tablib, librouteros, routeros-api, pyrad, django-freeradius, django-daraja, python-daraja, mpesa-sdk, pytest, pytest-django, factory-boy, Ruff, mypy, Playwright, FreeRADIUS, daloRADIUS, RADIUSdesk, OpenWISP, OpenWISP RADIUS, LibreQoS, PostgreSQL, Redis/Valkey, Tailwind, HTMX, and Caddy.

## 5. Adopt/Adapt/Reject Matrix

| Capability | Decision |
| --- | --- |
| Django auth/security/forms/templates | Adopt unchanged |
| Django REST Framework | Adopt for webhooks and versioned APIs only |
| HTMX/Tailwind | Adopt for operator UI |
| Phone normalization | Adopt behind wrapper |
| Daraja wrappers | Reject stale packages; build thin provider from official docs |
| Wallet and ledger | Implement minimally in-house |
| RouterOS packages | Evaluate behind wrapper |
| RADIUS CoA | Evaluate pyrad behind wrapper |
| FreeRADIUS SQL | Adopt as external integration boundary after licence review |
| Full ISP billing platforms | Use as architecture references only |

## 6. Licence Findings

Most Django/Python candidates are MIT, BSD, Apache-2.0, or similar permissive licences. FreeRADIUS is GPL-family and must be treated as an external system with explicit review before schema or packaging decisions. Redis server licence posture requires review versus Valkey. Packages with unclear metadata, including some ledger and RouterOS options, require Phase 1 licence review before adoption.

## 7. Proposed Data Model

See `docs/architecture/erd.md`. Key entities include Organization, StaffUser, Subscriber, Service, ServiceLocation, Plan, Subscription, Wallet, LedgerEntry, Payment, MpesaCallback, UnmatchedPayment, Invoice, Receipt, NASRouter, RadiusAccount, NetworkSession, ProvisioningJob, SupportTicket, and AuditEvent.

## 8. Paybill Workflow

Use Paybill account reference as the primary match signal. Normalize case and separators, preserve the original reference, never match by amount alone, and send missing or ambiguous references to unmatched payments.

## 9. Till Workflow

Till payments are lower-confidence. Match only through unique authorized payer phone, reliable unique historical mapping, supported reference data, or manual resolution. Never match by amount alone.

## 10. FreeRADIUS Design

Use FreeRADIUS as the RADIUS server and PostgreSQL-backed SQL integration as the operational boundary. Keep SuperSurf business-domain tables separate from FreeRADIUS tables and synchronize through provisioning services.

## 11. MikroTik Integration And Safety Design

Use `RouterOSAdapter` with fake, dry-run, and real API-TLS implementations. Default to dry-run. Only allow reviewed commands such as health checks, session listing, and subscriber disconnects. Do not alter WAN, routing, CAKE, WireGuard, watchdog, or unrelated settings.

## 12. Threat Model Summary

Primary risks are duplicate callbacks, forged callbacks, lost payments during network outages, unauthorized financial adjustments, secret leakage, CSV injection, ledger tampering, and unsafe router writes. Controls include idempotency, database constraints, strict validation, redaction, RBAC, append-only ledger, dry-run defaults, audit logging, dependency scanning, and restore tests.

## 13. Genuine Open Questions

See `docs/research/blocking-questions.md`. Main blockers are account-number format, packages/prices, renewal/grace/partial/overpayment policies, Paybill/Till product details, Daraja credentials, PPPoE username format, multi-service policy, RouterOS API certificate plan, RADIUS shared-secret plan, production OS, public domain, support/billing/NOC emails, and backup destination.

## 14. Phase 1 Dependency Shortlist

See `docs/reuse/dependency-shortlist.md`. Primary targets include Django 5.2 LTS, PostgreSQL, psycopg, Celery, django-celery-beat, django-htmx, django-filter, django-environ, django-axes, django-otp, phonenumbers, django-phonenumber-field, Babel, httpx, tenacity, structlog, pytest, pytest-django, factory-boy, Ruff, mypy, Playwright, and Caddy.

## 15. Phase 1 Implementation Checklist

See `docs/implementation/phase-1-checklist.md`.

## Stop Point

Phase 0 is complete. Do not begin Phase 1 until the owner explicitly approves.

