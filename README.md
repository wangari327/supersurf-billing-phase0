# SuperSurf Billing

SuperSurf Billing is a planned Kenya-first ISP billing and subscriber-management platform for SuperSurf.

This repository now contains Phase 0 documentation, Phase 0.5 architectural corrections, the Phase 1 lean Django foundation, the Phase 1.1 security-hardening correction, and the Phase 2 package catalog.

Phase 2 deliberately adds only the `billing.Plan` package catalog. It does not include subscribers, services, subscriptions, discounts, payments, wallets, ledger transactions, invoices, M-PESA implementation, FreeRADIUS provisioning, PPPoE, RouterOS integration, network provisioning, renewal automation, installation fees, equipment billing, customer portals, or live network actions.

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
- GitHub Actions CI

## Phase Boundary

Phase 2 is complete only for package catalog management. Do not begin Phase 3 without explicit owner approval.

Still absent:

- M-PESA implementation
- Subscribers
- Services
- Subscriptions
- Discounts
- Subscriber billing
- Invoices
- Wallets
- Ledger transactions
- FreeRADIUS provisioning
- PPPoE
- RouterOS integration
- Network provisioning
- Renewal automation
- Installation fees
- Equipment billing
- Customer portals
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

## Production Readiness

This bundle does not claim KRA, VAT, eTIMS, Communications Authority, data protection, payment-processing, or network-compliance certification. Those require separate reviewed implementation, testing, and legal or regulatory review where applicable.
