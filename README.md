# SuperSurf Billing

SuperSurf Billing is a planned Kenya-first ISP billing and subscriber-management platform for SuperSurf.

This repository now contains Phase 0 documentation, Phase 0.5 architectural corrections, the Phase 1 lean Django foundation, the Phase 1.1 security-hardening correction, the Phase 2 package catalog, the Phase 3 subscriber registry, Phase 4 package assignments, and Phase 5 billing periods.

Phase 5 deliberately adds only manual access-period records and manual renewals against the active subscription snapshot. It does not include billing charges, invoices, discounts, payments, wallets, ledger transactions, M-PESA implementation, automatic renewals, automatic expiry, automatic suspension, FreeRADIUS provisioning, PPPoE credentials, RouterOS integration, network provisioning, installation fees, equipment billing, customer portals, notifications, or live network actions.

## Current Deliverables

- SuperSurf product and brand contract
- Kenya-specific defaults and subscriber data conventions
- Official documentation research
- Open-source and package reconnaissance
- Reuse and dependency shortlist
- Licence review and third-party notices
- Proposed modular-monolith architecture
- Entity-relationship model
- Paybill and Till workflows
- FreeRADIUS and MikroTik integration design
- Network safety model
- Threat model and permission model
- Backup design
- ADRs for the initial technical direction
- Phase 1 implementation checklist
- Genuine blocking questions
- Django 5.2.16 LTS foundation
- SuperSurf and Kenya default seed migration
- Custom user model
- Staff roles using Django Groups and Permissions
- Append-only application audit model
- Operator shell pages
- Health and readiness endpoints
- Minimal Celery broker/worker wiring
- Development-only Docker Compose definitions for web, PostgreSQL, Valkey broker, worker, and scheduler
- Phase 1.1 security hardening for redaction, role boundaries, admin bypass prevention, sensitive settings permissions, production fail-closed settings, and audit append-only behavior
- Phase 2 package catalog with KSh minor-unit pricing, initial SuperSurf packages, audited package management, and deactivation/reactivation workflows
- Phase 3 subscriber registry with generated subscriber account numbers, generated service references, Kenya phone normalization, audited profile/status workflows, and view-only access for non-admin operator roles
- Phase 4 manual package assignment with immutable package snapshots and subscription history
- Phase 5 manual billing periods, manual renewal date rules, derived billing state, duplicate-operation protection, and paginated period history
- GitHub Actions CI

## Phase Boundary

Phase 5 is complete only for manual billing periods and manual renewals. Manual renewal records do not claim payment receipt. Do not begin the next phase without explicit owner approval.

Still absent:

- M-PESA implementation
- Discounts
- Billing charges
- Subscriber billing
- Invoices
- Wallets
- Ledger transactions
- FreeRADIUS provisioning
- PPPoE
- RouterOS integration
- Network provisioning
- Automatic renewals
- Automatic expiry
- Automatic suspension
- Grace-state automation
- Renewal automation
- Installation fees
- Equipment billing
- Customer portals
- Notifications
- Live network actions
- Production credentials
- Fake production domains, emails, Paybill numbers, Till numbers, or credentials

## Local Setup

Recommended setup uses `uv`:

```powershell
uv sync
npm ci --include=optional
npm run build:css
uv run python manage.py migrate
uv run python manage.py seed_roles
uv run python manage.py create_first_owner --username owner --email ""
uv run python manage.py runserver
```

If `uv` is not installed, see `docs/development/dependency-management.md`.

## Review Path

Start with:

1. `docs/product/supersurf-brand.md`
2. `docs/kenya/product-defaults.md`
3. `docs/architecture/overview.md`
4. `docs/reuse/component-research.md`
5. `docs/architecture/threat-model.md`
6. `docs/implementation/phase-1-checklist.md`
7. `docs/research/blocking-questions.md`
8. `docs/development/local-setup.md`
9. `docs/operations/first-owner.md`
10. `docs/implementation/phase-2-package-catalog.md`
11. `docs/implementation/phase-3-subscriber-registry.md`
12. `docs/implementation/phase-4-package-assignments.md`
13. `docs/implementation/phase-5-billing-periods.md`

## Production Readiness

This bundle does not claim KRA, VAT, eTIMS, Communications Authority, data protection, payment-processing, or network-compliance certification. Those require separate reviewed implementation, testing, and legal or regulatory review where applicable.
